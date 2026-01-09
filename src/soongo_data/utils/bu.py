import json
import logging
import os
import typing

import pandas as pd
import sqlalchemy as sa

from soongo_data.data_models import (AccidentsModel, BusinessUnitsModel, CollaboratorsModel,
                                     SoonGoRecordsModel, VehiclesModel)
from soongo_data.sql_mappings import (AccidentsTable, BusinessUnitsTable, CollaboratorsTable,
                                      VehicleBusinessUnitView, OrganizationsTable)
from soongo_data.utils.db import gen_engine
from soongo_data.utils.type import str_is_nan


def get_business_units(
    entity_df: pd.DataFrame,
    logger: logging.Logger,
    organization_name: str,
    mapping_col: typing.Optional[str] = None,
    source_connectors_override: typing.Optional[list] = None,
) -> pd.DataFrame:
    """ Get Business units.

    If connector amongst source connectors for that organization, then
    build business units from entities. If not but one entity provided, map
    entity to business units. Otherwise, return empty.

    :param entity_df: pandas DataFrame containing entity data to be aggregated
    as a business unit
    :param logger: logger
    :param organization_name: organization_name
    :param mapping_col: column to map entities to business units. If not specified
    using the mapping column name specified in the bu correction dictionary params

    :returns: df with business_unit column, drops entities if used
    """
    bu_df = get_db_bu(
        organization_name=organization_name,
    )
    correction_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            'bu_correction.json',
        )
    )
    with open(
        correction_path
    ) as correction_file:
        org_dict = json.load(correction_file)
        assert organization_name in org_dict, (
            'Error in the bu correction dictionary - should have'
            'keys for each organization'
        )
        org_dict = org_dict[organization_name]
        assert 'params' in org_dict, (
            'Error in the bu correction dictionary - should have'
            'params keys for each organization'
        )
        if source_connectors_override is None:
            source_connectors = org_dict['params']['source_connectors']
        else:
            source_connectors = source_connectors_override
        bu_cols = org_dict['params']['bu_cols']
        mapping_col = org_dict['params'].get('mapping_col') if not mapping_col else mapping_col
        bu_dict = org_dict.get('bus')

    if BusinessUnitsModel.business_unit.name not in entity_df.columns:
        entity_df[BusinessUnitsModel.business_unit.name] = ''

    assert SoonGoRecordsModel.connector_name.name in entity_df.columns, (
        'Connector name should be in the entity dataframe'
    )
    if '*' not in source_connectors:
        is_source_connector = entity_df[SoonGoRecordsModel.connector_name.name].isin(
            source_connectors
        )
    else:
        is_source_connector = pd.Series(
            [True] * entity_df.shape[0],
            index=entity_df.index,
        )
    no_bu_at_start = str_is_nan(entity_df[BusinessUnitsModel.business_unit.name])
    if set(bu_cols).issubset(entity_df.columns):
        logger.info(
            'Building business units from entities for organization %s for %d rows from connectors %s',
            organization_name,
            is_source_connector.sum(),
            source_connectors,
        )
        for bu_col in bu_cols:
            entity_df[BusinessUnitsModel.business_unit.name] = (
                entity_df[BusinessUnitsModel.business_unit.name].mask(
                    is_source_connector & ~str_is_nan(entity_df[bu_col]) & no_bu_at_start,
                    entity_df[BusinessUnitsModel.business_unit.name] + ' > ' + entity_df[bu_col],
                )
            )
            entity_df[BusinessUnitsModel.business_unit.name] = (
                entity_df[BusinessUnitsModel.business_unit.name].str.strip(' > ')
            )

    if mapping_col in entity_df.columns and (bu_dict is not None):
        logger.info(
            'Mapping business units from provided dictionary for organization %s',
            organization_name,
        )
        if mapping_col == BusinessUnitsModel.business_unit.name:
            no_bu_at_start = True  # We want then to replace existing business units
        missing_bus = set(
            entity_df.loc[~str_is_nan(entity_df[mapping_col]), mapping_col]
        ).difference(bu_dict.keys())
        logger.warning(
            f'All mapping values should be in the dictionary but {missing_bus}'
            ' are missing'
        )
        replacement_bu = entity_df[mapping_col].map(bu_dict)

        entity_df[BusinessUnitsModel.business_unit.name] = (
            entity_df[BusinessUnitsModel.business_unit.name].mask(
                ~is_source_connector & no_bu_at_start & ~str_is_nan(replacement_bu),
                replacement_bu,
            )
        )

    elif mapping_col in entity_df.columns:
        bu_df = bu_df.rename(
            columns={
                'name': mapping_col,
                BusinessUnitsModel.business_unit.name: 'bu_temp'
            }
        )
        logger.info(
            'Mapping business units from database for organization %s',
            organization_name,
        )
        dup_mapping_cols = bu_df[mapping_col].duplicated(False)
        if dup_mapping_cols.any():
            logger.error(
                'Not mapping %d groups because mapping col %s is duplicated',
                dup_mapping_cols.sum(),
                mapping_col,
            )

        bu_df = bu_df.loc[
            ~dup_mapping_cols,
            [
                mapping_col,
                'bu_temp'
            ]
        ]
        entity_df = entity_df.merge(
            bu_df,
            on=mapping_col,
            how='left',
            validate='m:1',
            indicator='_groups',
        )
        entity_df[BusinessUnitsModel.business_unit.name] = (
            entity_df[BusinessUnitsModel.business_unit.name].mask(
                str_is_nan(
                    entity_df[BusinessUnitsModel.business_unit.name]
                ),
                entity_df['bu_temp'],
            )
        )

        missing_bus = entity_df.loc[
            ~str_is_nan(entity_df[mapping_col]) & (entity_df['_groups'] != 'both'),
            mapping_col
        ].unique()
        logger.warning(
            f'All mapping values should be the db but {missing_bus}'
            ' are missing'
        )

    return entity_df


def get_db_bu(
    organization_name: str,
) -> pd.DataFrame:
    """ Get business units from the database

    :param organization_name: organization_name
    :param mapping_col: column to map entities to business units

    :returns: df with business_unit_id column, drops entities if used
    """
    db_engine = gen_engine(database_url=os.environ['DATABASE_URL'])
    with db_engine.connect() as connection:
        group_df = pd.read_sql(
            sql=sa.select(
                BusinessUnitsTable.name,
                BusinessUnitsTable.id.label(BusinessUnitsModel.business_unit_id.name + '_0'),
                BusinessUnitsTable.parent_id.label(BusinessUnitsModel.business_unit_id.name + '_1'),
            ).select_from(
                BusinessUnitsTable
            ).join(
                OrganizationsTable,
                BusinessUnitsTable.organization_id == OrganizationsTable.id,
            ).where(
                OrganizationsTable.slug == organization_name
            ),
            con=connection,
        )

    i = 1
    while pd.notna(group_df[BusinessUnitsModel.business_unit_id.name + f'_{i}']).any():
        parent_df = group_df[
            [
                # We must always use the original mapping col and id
                # and its original parent so that we find the original
                # name, id and parent of the business unit
                'name',
                BusinessUnitsModel.business_unit_id.name + f'_{0}',
                BusinessUnitsModel.business_unit_id.name + f'_{1}'
            ]
        ]
        renaming_dict = {
            'name': f'name_{i}',
            BusinessUnitsModel.business_unit_id.name + f'_{0}': BusinessUnitsModel.business_unit_id.name + f'_{i}',
            BusinessUnitsModel.business_unit_id.name + f'_{1}': BusinessUnitsModel.business_unit_id.name + f'_{i + 1}',
        }
        parent_df = parent_df.rename(
            renaming_dict,
            axis=1,
        )
        group_df = group_df.merge(
            parent_df,
            how='left',
            on=BusinessUnitsModel.business_unit_id.name + f'_{i}',
        )
        i += 1

    group_df[BusinessUnitsModel.business_unit.name] = group_df[
        sorted(
            [
                col for col in group_df.columns
                if col.startswith('name')
            ],
            reverse=True,
        )
    ].apply(
        lambda x: ' > '.join([value for value in x.tolist() if pd.notna(value)]),
        axis=1,
    )
    group_df.rename(
        columns={
            BusinessUnitsModel.business_unit_id.name + f'_{0}': BusinessUnitsModel.business_unit_id.name,
        },
        inplace=True,
    )

    return group_df[
        [
            'name',
            BusinessUnitsModel.business_unit_id.name,
            BusinessUnitsModel.business_unit.name,
        ]
    ]


def get_cost_center(
    data_df: pd.DataFrame,
    logger: logging.Logger,
    organization_name: str,
    date_col: typing.Optional[str] = None,
) -> pd.DataFrame:
    """ Get cost center

    Requires one of the following columns:
    - plate_number
    - soongo_collab_reference

    Fetches the cost center from the database using the collaborators table
    and the collaborators_vehicles table

    :param data_df: pandas DataFrame containing entity data to be aggregated as a
    business unit
    :param logger: logger
    :param organization_name: organization_name

    :returns: df with no entity columns left but a cost center column, if the entities
    where available as a business unit id
    """
    id_cols = {
        VehiclesModel.plate_number.name,
        CollaboratorsModel.employee_full_name.name,
    }
    available_cols = set(data_df.columns).intersection(id_cols)
    if not available_cols:
        raise ValueError(
            'No plate number or collaborator reference in the dataframe'
        )
    if BusinessUnitsModel.business_unit_id.name not in data_df.columns:
        data_df[BusinessUnitsModel.business_unit_id.name] = None
    logger.info(
        'Starting with %d business_unit_ids out of %d rows',
        (~str_is_nan(data_df[BusinessUnitsModel.business_unit_id.name])).sum(),
        data_df.shape[0],
    )

    db_engine = gen_engine(database_url=os.environ['DATABASE_URL'])
    nb_expenses = len(data_df)

    attempts = 0
    while attempts < 3:
        try:
            connection = db_engine.connect()
            attempts += 1
        except sa.exc.OperationalError as e:
            logger.error(
                'Database connection error: %s',
                str(e),
            )
        else:
            break

        if attempts == 3:
            logger.error(
                'Failed to connect to the database after 3 attempts'
            )
            raise

    accident_bu = 0
    if AccidentsModel.accident_ref.name in data_df.columns:
        accident_query = sa.select(
            AccidentsTable.accident_ref.label(AccidentsModel.accident_ref.name),
            sa.func.coalesce(
                CollaboratorsTable.business_unit_id,
                VehicleBusinessUnitView.cost_center_id
            ).label('accident_business_unit_id'),
        ).select_from(
            AccidentsTable
        ).outerjoin(
            CollaboratorsTable,
            AccidentsTable.collaborator_id == CollaboratorsTable.id,
        ).outerjoin(
            VehicleBusinessUnitView,
            sa.and_(
                AccidentsTable.vehicle_id == VehicleBusinessUnitView.vehicle_id,
                VehicleBusinessUnitView.date_from <= AccidentsTable.accident_date,
                sa.func.coalesce(
                    VehicleBusinessUnitView.date_to,
                    sa.func.now()
                ) >= AccidentsTable.accident_date,
            )
        ).where(
            AccidentsTable.organization_id == sa.select(
                OrganizationsTable.id
            ).where(
                OrganizationsTable.slug == organization_name
            ),
            AccidentsTable.accident_ref.is_not(None),
        )
        accident_df = pd.read_sql(
            sql=accident_query,
            con=connection,
        )
        data_df = data_df.merge(
            accident_df,
            how='left',
            on=AccidentsModel.accident_ref.name,
            validate='m:1',
        )
        data_df[BusinessUnitsModel.business_unit_id.name] = (
            data_df[BusinessUnitsModel.business_unit_id.name].mask(
                str_is_nan(
                    data_df[BusinessUnitsModel.business_unit_id.name]
                ),
                data_df['accident_business_unit_id'],
            )
        )
        data_df.drop(
            ['accident_business_unit_id'],
            axis=1,
            inplace=True,
        )
        accident_bu = (
            data_df[BusinessUnitsModel.business_unit_id.name].notna().sum()
        )
        logger.info(
            'Fetched %d business units from collaborators out of %d rows',
            accident_bu,
            data_df.shape[0],
        )

    collab_bu = 0
    if CollaboratorsModel.employee_full_name.name in available_cols:
        collaborator_query = sa.select(
            CollaboratorsTable.soongo_collab_reference.label(
                CollaboratorsModel.employee_full_name.name
            ),
            CollaboratorsTable.business_unit_id.label(
                'collab_business_unit_id'
            ),
        ).select_from(CollaboratorsTable).where(
            CollaboratorsTable.organization_id == sa.select(
                OrganizationsTable.id
            ).where(
                OrganizationsTable.slug == organization_name
            )
        )
        collaborators_df = pd.read_sql(
            sql=collaborator_query,
            con=connection,
        )
        data_df = data_df.merge(
            collaborators_df,
            how='left',
            on=CollaboratorsModel.employee_full_name.name,
            validate='m:1',
        )
        data_df[BusinessUnitsModel.business_unit_id.name] = (
            data_df[BusinessUnitsModel.business_unit_id.name].mask(
                str_is_nan(
                    data_df[BusinessUnitsModel.business_unit_id.name]
                ),
                data_df['collab_business_unit_id'],
            )
        )
        data_df.drop(
            ['collab_business_unit_id'],
            axis=1,
            inplace=True,
        )
        collab_bu = (
            data_df[BusinessUnitsModel.business_unit_id.name].notna().sum()
        )
        logger.info(
            'Fetched %d business units from collaborators out of %d rows',
            collab_bu,
            data_df.shape[0],
        )

    if VehiclesModel.plate_number.name in available_cols:
        vehicles_query = sa.text(
            """
            SELECT
                vehicles.plate_number,
                vehicle_bu.cost_center_id as vehicle_business_unit_id,
                vehicle_bu.date_from as vehicle_date_from,
                vehicle_bu.date_to as vehicle_date_to,
                vehicle_bu.rank as vehicle_rank
            FROM publ.vehicle_business_unit_view AS vehicle_bu
            JOIN publ.vehicles
                ON vehicle_bu.vehicle_id = vehicles.id
            JOIN common.organizations
                ON vehicles.organization_id = organizations.id
                AND organizations.slug = :organization_name
            """
        )
        vehicles_df = pd.read_sql(
            sql=vehicles_query,
            con=connection,
            params={
                'organization_name': organization_name
            },
        )
        no_bu = str_is_nan(vehicles_df['vehicle_business_unit_id']).any()
        if date_col is None and not no_bu:
            vehicles_df = vehicles_df.loc[
                vehicles_df['vehicle_rank'] == 1,
                [
                    VehiclesModel.plate_number.name,
                    'vehicle_business_unit_id',
                ],
            ]
            data_df = data_df.merge(
                vehicles_df,
                how='left',
                on=VehiclesModel.plate_number.name,
                validate='m:1',
            )
            data_df[BusinessUnitsModel.business_unit_id.name] = (
                data_df[BusinessUnitsModel.business_unit_id.name].mask(
                    str_is_nan(
                        data_df[BusinessUnitsModel.business_unit_id.name]
                    ),
                    data_df['vehicle_business_unit_id'],
                )
            )
            data_df.drop(
                ['vehicle_business_unit_id'],
                axis=1,
                inplace=True,
            )
            return data_df

        # If date_col is specified, we need to filter the vehicles_df
        # to apply the correct association at the correct date
        data_df.reset_index(drop=False, inplace=True, names='old_index')
        assert data_df['old_index'].is_unique, (
            'Dataframe should be unique before the merge'
        )
        data_df = data_df.merge(
            vehicles_df,
            how='left',
            on=VehiclesModel.plate_number.name,
            validate='m:m',
            indicator='_merge',
        )
        data_df['vehicle_date_to'].fillna(
            data_df[date_col].max(),
            inplace=True,
        )

        # We need to handle three cases:
        # 1- the date_col is between date_from and date_to
        # 2- the date_col is NaT - then business_unit_id is NAT and dedup
        # 3- the date_col is not between date_from and date_to but not NaT

        # If one of the original rows matched a vehicle_bu assignment using
        # the date_col, we need to keep it and drop the others
        # otherwise, we just keep rank 1 and replace the business_unit_id
        # with null
        data_df['is_matched'] = (
            (data_df[date_col] >= data_df['vehicle_date_from']) &
            (data_df[date_col] <= data_df['vehicle_date_to'])
        )
        data_df['is_matched'] = data_df['is_matched'].fillna(False)
        data_df['index_is_matched'] = data_df.groupby(
            ['old_index']
        )['is_matched'].transform('max')
        not_merged = data_df['_merge'] == 'left_only'
        data_df = data_df.loc[
            data_df['is_matched']
            |
            # Some vehicles will have entries in the date_from date_to table
            # but not for the correct dates. In that case, filter based on rank
            # just to ensure unicity, but later mask the business_unit_id
            (
                ~data_df['index_is_matched'] &
                (data_df['vehicle_rank'] == 1)
            )
            | not_merged
        ]
        assert len(data_df) == nb_expenses, (
            'Dataframe should not change size after the filtering'
        )
        assert data_df['old_index'].is_unique, (
            'Dataframe should be unique after filtering'
        )
        missing_bu = str_is_nan(
            data_df[BusinessUnitsModel.business_unit_id.name]
        )
        data_df[BusinessUnitsModel.business_unit_id.name] = (
            data_df[BusinessUnitsModel.business_unit_id.name].mask(
                missing_bu & data_df['is_matched'],
                data_df['vehicle_business_unit_id'],
            )
        )
        data_df.drop(
            [
                'old_index',
                'vehicle_business_unit_id',
                'is_matched',
                'index_is_matched',
                'vehicle_rank',
                'vehicle_date_from',
                'vehicle_date_to',
            ],
            axis=1,
            inplace=True,
        )

    connection.close()

    # Slight inefficiency in fetching the business unit " > " in a separate
    # query rather than within the original query but allows
    # to use only one logic across the ETL.
    bu_df = get_db_bu(organization_name=organization_name)
    bu_df.rename({BusinessUnitsModel.business_unit.name: 'temp_bu'}, axis=1, inplace=True)
    data_df = data_df.merge(
        bu_df[
            [
                BusinessUnitsModel.business_unit_id.name,
                'temp_bu',
            ]
        ],
        how='left',
        on=BusinessUnitsModel.business_unit_id.name,
        validate='m:1',
    )
    data_df[BusinessUnitsModel.business_unit.name] = (
        data_df[BusinessUnitsModel.business_unit.name].mask(
            str_is_nan(data_df[BusinessUnitsModel.business_unit.name]),
            data_df['temp_bu'],
        )
    )

    assert len(data_df) == nb_expenses, (
        'Dataframe should not change size after the merge'
    )
    return data_df


def update_bu_dict(
    bu_dict: dict,
    organization_name: str,
):
    """ Update the bu correction dictionary with the bu dict

    :param bu_dict: dictionary of entities to business units
    :param organization_name: the name of the organization
    """
    with open(
        os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                'bu_correction.json',
            )
        )
    ) as correction_file:
        correction_dict = json.load(correction_file)

    if organization_name not in correction_dict:
        raise ValueError(
            f'Organization {organization_name} not in the correction dictionary'
        )

    org_dict = correction_dict[organization_name]
    assert 'bus' in org_dict, (
        'Error in the bu correction dictionary - should have'
        'bus and params keys for each organization'
    )

    for mapping_value, business_unit in bu_dict.items():
        correction_dict[organization_name]['bus'][mapping_value] = business_unit

    with open(
        os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                'bu_correction.json',
            )
        ),
        'w',
    ) as correction_file:
        json.dump(correction_dict, correction_file, indent=4)


def correct_business_unit(
    entity_df: pd.DataFrame,
    logger: logging.Logger,
    organization_name: str,
) -> pd.DataFrame:
    """ Get Business units.

    If connector amongst source connectors for that organization, then
    build business units from entities. If not but one entity provided, map
    entity to business units. Otherwise, return empty.

    :param entity_df: pandas DataFrame containing entity data to be aggregated
    as a business unit
    :param logger: logger
    :param organization_name: organization_name
    :param mapping_col: column to map entities to business units. If not specified
    using the mapping column name specified in the bu correction dictionary params

    :returns: df with business_unit column, drops entities if used
    """
    correction_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            'bu_correction.json',
        )
    )
    with open(
        correction_path
    ) as correction_file:
        org_dict = json.load(correction_file)
        assert organization_name in org_dict, (
            'Error in the bu correction dictionary - should have'
            'keys for each organization'
        )
        org_dict = org_dict[organization_name]

        bu_dict = org_dict.get('bus')

    if BusinessUnitsModel.business_unit.name in entity_df.columns and (bu_dict is not None):
        logger.info(
            'Mapping business units from provided dictionary for organization %s',
            organization_name,
        )

        replacement_bu = entity_df[BusinessUnitsModel.business_unit.name].map(bu_dict)

        entity_df[BusinessUnitsModel.business_unit.name] = (
            entity_df[BusinessUnitsModel.business_unit.name].mask(
                ~str_is_nan(replacement_bu),
                replacement_bu,
            )
        )

    return entity_df
