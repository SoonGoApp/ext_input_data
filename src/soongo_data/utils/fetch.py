""" Fetch utility functions

Functions to fetch specific informations from db
"""
from __future__ import annotations

import logging
import os
from typing import Set, TYPE_CHECKING, Any

import pandas as pd
import sqlalchemy as sa

from soongo_data.data_models import (
    CollaboratorsModel, ExpensesModel,
    SoonGoRecordsModel, VehicleAssociationsModel,
    VehiclesModel
)
from soongo_data.input_tables.vehicles_table import VehiclesInputTable
from soongo_data.sql_mappings import (OrganizationsTable, OrganizationParametersTable,
                                      VehicleBrandsTable,
                                      VehicleContractsTable,
                                      VehicleModelsTable, VehiclesTable,
                                      VehicleTrimsTable, SuppliersTable)
from soongo_data.utils.db import gen_engine
from soongo_data.utils.type import str_is_nan, DateConverter, series_is_nan


if TYPE_CHECKING:
    from soongo_data.connectors.full_data import ConnectorData


def fetch_vehicle_data(
    df: pd.DataFrame,
    cols_to_fetch: Set[str],
    connector_data: ConnectorData,
    logger: logging.Logger,
) -> pd.DataFrame:
    """ Fetch columns of interest from the vehicle table

    :param df: Pandas DataFrame to enrich. Must have either plate_number or
    employee_id
    :param cols_to_fetch: list of columns to fetch. Must be among vehicle_table
    columns.
    :param connector_data: Connector Data with all data for the organisation

    :return: enriched df with additional columns
    """
    if VehiclesModel.plate_number.name not in df.columns:
        raise ValueError(
            'Plate number must be provided'
        )

    db_engine = gen_engine(database_url=os.environ['DATABASE_URL'])
    with db_engine.connect() as connection:
        vehicle_df = pd.read_sql(
            sql=sa.select(
                VehiclesTable,
                VehicleModelsTable.name.label(VehiclesModel.model.name),
                VehicleBrandsTable.name.label(VehiclesModel.make.name),
                VehicleTrimsTable.name.label(VehiclesModel.full_model.name),
            ).select_from(
                VehiclesTable
            ).outerjoin(
                VehicleModelsTable,
                VehiclesTable.model_id == VehicleModelsTable.id,
            ).outerjoin(
                VehicleBrandsTable,
                VehiclesTable.brand_id == VehicleBrandsTable.id,
            ).outerjoin(
                VehicleTrimsTable,
                VehiclesTable.trim_id == VehicleTrimsTable.id,
            ).join(
                OrganizationsTable,
                sa.and_(
                    OrganizationsTable.id == VehiclesTable.organization_id,
                    OrganizationsTable.slug == connector_data.organization_name,
                ),
            ),
            con=connection,
        )
        vehicle_df = vehicle_df.rename(
            columns={
                input_col.sql_name: input_col.name for input_col
                in VehiclesInputTable().columns
            },  # Inverse mapping
        )

    df = df.merge(
        vehicle_df[[VehiclesModel.plate_number.name] + list(cols_to_fetch)],
        on=VehiclesModel.plate_number.name,
        how='left',
        validate='m:1',
        indicator=True,
        suffixes=('_before_fetch', '_after_fetch'),
    )
    old_columns = [col for col in df.columns if col.endswith('_before_fetch')]
    for old_col in old_columns:
        new_col = old_col[:len('_before_fetch')*-1]
        fetched_col = new_col + '_after_fetch'
        df[new_col] = df[old_col].mask(
            series_is_nan(df[old_col]),
            df[fetched_col]
        )
        df.drop(
            [old_col, fetched_col],
            axis=1,
            inplace=True
        )

    missing_plates = df.loc[
        ~str_is_nan(df[VehiclesModel.plate_number.name])
        & (df['_merge'] == 'left_only'),
        VehiclesModel.plate_number.name,
    ].unique()
    if missing_plates.any():
        logger.warning(
            '%d out of %d plates are missing in database for organization %s:  %s',
            len(missing_plates),
            len(df[VehiclesModel.plate_number.name].unique()),
            missing_plates,
            connector_data.organization_name,
        )
    df.drop(columns='_merge', inplace=True)
    return df


def fetch_plate_from_collab(
    df: pd.DataFrame,
    connector_data: ConnectorData,
    logger: logging.Logger,
    date_var: str = SoonGoRecordsModel.record_date.name,
) -> pd.DataFrame:
    """ Fetch company vehicle plate_number from a Series of collaborator_id

    :param df: Pandas DataFrame to enrich. Must have either plate_number or
        employee_id
    :param id_var: column name uniquely identifying rows to help deduplicate
        entries.
    :param date_var: column
    :param connector_data: Connector Data with all data for the organisation

    :return: df with additional plate_number column
    """
    if CollaboratorsModel.soongo_collab_reference.name not in df.columns:
        raise ValueError(
            'Plate number must be provided'
        )
    if df.index.unique:
        df['temp_row_id'] = df.index
    else:
        df['temp_row_id'] = df.reset_index().index

    association_df = VehicleAssociationsInputTable().get(
        connector_data=connector_data,
        logger=logger,
    )

    df = df.merge(
        association_df[
            [
                VehiclesModel.plate_number.name,
                CollaboratorsModel.soongo_collab_reference.name,
                VehicleAssociationsModel.association_start_date.name,
                VehicleAssociationsModel.association_end_date.name,
            ]
        ],
        on=CollaboratorsModel.soongo_collab_reference.name,
        how='left',
        indicator=('_1', '_2'),
    )
    if 'plate_number_1' in df.columns:
        df[VehiclesModel.plate_number.name] = (
            df['plate_number_1'].fillna(df['plate_number_2'])
        )
        df.drop(['plate_number_1', 'plate_number_2'], axis=1, inplace=True)

    df = df.loc[
        (df[date_var] >= df[VehicleAssociationsModel.association_start_date.name])
        &
        (
            (df[date_var] <= df[VehicleAssociationsModel.association_end_date.name])
            |
            pd.isna(df[VehicleAssociationsModel.association_end_date.name])
        )
    ]
    df['min_start_date'] = df.groupby('temp_row_id')[
        VehicleAssociationsModel.association_start_date.name
    ].transform('min')
    df['temp_end_date'] = (
        df[VehicleAssociationsModel.association_end_date.name].fillna(
            df[date_var].max(),  # Filler which cannot be exceeded
        )
    )
    df['max_start_date'] = df.groupby('temp_row_id')[
        'temp_end_date'
    ].transform('max')
    df = df.loc[
        (
            (df[VehicleAssociationsModel.association_start_date.name] == df['min_start_date'])
            &
            (df['max_start_date'] == df['max_start_date'])
        ) |
        # If association_start_date is na, then no association (mandatory col)
        pd.isna(df[VehicleAssociationsModel.association_start_date.name])
    ]
    assert df['temp_row_id'].unique
    df = df.drop('temp_row_id', axis=1)
    return df


def fetch_contract_data(
    df: pd.DataFrame,
    cols_to_fetch: Set[str],
    organization_slug: str,
    logger: logging.Logger,
) -> pd.DataFrame:
    """ Fetch columns of interest from the vehicle table

    :param df: Pandas DataFrame to enrich. Must have either plate_number or
    employee_id
    :param cols_to_fetch: list of columns to fetch. Must be among vehicle_contracts
    columns.
    :param organization_slug: Slug of the organization

    :return: enriched df with additional columns
    """
    available_cols = set(cols_to_fetch).intersection(df.columns)
    if available_cols:
        logger.error(
            'Asked to fetch %s but already available',
            available_cols,
        )
    missing_cols = set(cols_to_fetch).difference(df.columns)

    if VehiclesModel.plate_number.name not in df.columns:
        raise ValueError(
            'Plate number must be provided'
        )

    original_count = len(df)

    db_engine = gen_engine(database_url=os.environ['DATABASE_URL'])

    with db_engine.connect() as connection:
        contracts_df = pd.read_sql(
            sql=sa.select(
                VehicleContractsTable,
                VehiclesTable.plate_number.label(VehiclesModel.plate_number.name),
                SuppliersTable.name.label(VehiclesModel.car_supplier.name),
                sa.func.rank().over(
                    partition_by=VehiclesTable.plate_number,
                    order_by=(
                        VehicleContractsTable.date_from.desc(),
                        sa.func.coalesce(
                            VehicleContractsTable.date_to,
                            sa.func.current_date()
                        ).desc(),
                        VehicleContractsTable.id,  # tie breaker
                    ),
                ).label('vehicle_rank'),
            ).select_from(
                VehicleContractsTable
            ).join(
                VehiclesTable,
                VehicleContractsTable.vehicle_id == VehiclesTable.id,
            ).outerjoin(
                SuppliersTable,
                SuppliersTable.id == VehicleContractsTable.supplier_id,
            ).join(
                OrganizationsTable,
                sa.and_(
                    OrganizationsTable.id == VehiclesTable.organization_id,
                    OrganizationsTable.slug == organization_slug,
                ),
            ),
            con=connection,
        )

    # If date_col is specified, we need to filter the vehicles_df
    # to apply the correct association at the correct date
    df.reset_index(drop=False, inplace=True, names='old_index')
    assert df['old_index'].is_unique, (
        'Dataframe should be unique before the merge'
    )
    cols_to_fetch = missing_cols.union(
        [
            VehiclesModel.plate_number.name,
            'vehicle_rank',
            'date_to',
            'date_from',
        ]
    )
    df = df.merge(
        contracts_df[list(cols_to_fetch)],
        how='left',
        on=VehiclesModel.plate_number.name,
        validate='m:m',
        indicator='_merge',
    )

    df['date_to'] = DateConverter(
        date_format=r'%Y-%m-%d %H:%M:%S',
        force_format=True
    )(df['date_to'])
    df['date_to'] = df['date_to'].dt.tz_localize(None).fillna(
            df[ExpensesModel.billing_date.name].max() + pd.Timedelta(seconds=1)
    ).mask(df['_merge'] == 'left_only', pd.NaT)
    df['date_from'] = DateConverter(
        date_format=r'%Y-%m-%d %H:%M:%S',
        force_format=True
    )(df['date_from']).dt.tz_localize(None)

    # We need to handle three cases:
    # 1- the date_col is between date_from and date_to
    # 2- the date_col is NaT - then business_unit_id is NAT and dedup
    # 3- the date_col is not between date_from and date_to but not NaT

    # If one of the original rows matched a vehicle_bu assignment using
    # the date_col, we need to keep it and drop the others
    # otherwise, we just keep rank 1 and replace the business_unit_id
    # with null
    df['is_matched'] = (
        (df[ExpensesModel.billing_date.name] >= df['date_from']) &
        (df[ExpensesModel.billing_date.name] < df['date_to'])
    )
    df['is_matched'] = df['is_matched'].fillna(False)
    df['index_is_matched'] = df.groupby(
        ['old_index']
    )['is_matched'].transform('max')
    not_merged = df['_merge'] == 'left_only'
    df = df.loc[
        df['is_matched']
        |
        # Some vehicles will have entries in the date_from date_to table
        # but not for the correct dates. In that case, filter based on rank
        # just to ensure unicity, but later mask the business_unit_id
        (
            ~df['index_is_matched'] &
            (df['vehicle_rank'] == 1)
        )
        | not_merged
    ]
    assert len(df) == original_count, (
        'Dataframe should not change size after the filtering'
    )
    assert df['old_index'].is_unique, (
        'Dataframe should be unique after filtering'
    )
    df.drop(
        [
            'old_index',
            'is_matched',
            'index_is_matched',
            'vehicle_rank',
            'date_from',
            'date_to',
            '_merge',
        ],
        axis=1,
        inplace=True,
    )

    return df


def get_org_param(organization_name: str, param_name: str) -> Any:
    db_engine = gen_engine(database_url=os.environ['DATABASE_URL'])
    with db_engine.connect() as connection:
        return connection.execute(
            sa.select(
                OrganizationParametersTable.value['value']
            ).select_from(
                OrganizationParametersTable
            ).join(
                OrganizationsTable,
                sa.and_(
                    OrganizationsTable.id == OrganizationParametersTable.organization_id,
                    OrganizationsTable.slug == organization_name,
                    OrganizationParametersTable.name == param_name,
                    sa.func.now().between(
                        sa.func.coalesce(
                            OrganizationParametersTable.date_from,
                            sa.func.now(),
                        ),
                        sa.func.coalesce(
                            OrganizationParametersTable.date_to,
                            sa.func.now()
                        ),
                    )
                )
            )
        ).scalar()
