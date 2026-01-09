""" Script to calculate the vehicle table on which to compute impacts."""
import logging
import os
import typing
from datetime import datetime

import numpy as np
import pandas as pd
import sqlalchemy as sa

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (SoonGoRecordsModel, VehicleContractsModel,
                                     VehiclesModel)
from soongo_data.sql_mappings import (OrganizationParametersTable,
                                      VehicleContractsTable)
from soongo_data.utils.enums import ContractType, FiscalType
from soongo_data.utils.fetch import fetch_vehicle_data
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id,
                                            fetch_organization_params,
                                            keep_duplicates)
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.type import series_is_nan, str_is_nan, get_dtype_null

pd.set_option('future.no_silent_downcasting', True)

DEFAULT_VALIDATION_PARAMS = {
    "lease_months": 0,
    "lease_mileage": 0,
    "lease_end_date": 1,
    "lease_start_date": 1,
    "total_rent_tax_exc": 1,
}

@add_input_table
class VehicleContractsInputTable(InputTable):

    def __init__(self):
        super().__init__(
            sql_mapping=VehicleContractsTable,
            columns=[
                InputColumn.from_data_column(
                    column=VehiclesModel.plate_number,
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.contract_reference,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.lease_start_date,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.lease_end_date,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.lease_months,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.lease_mileage,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.contract_start_date,
                    sliding_col='start',
                    sql_name='date_from',
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.contract_end_date,
                    sliding_col='end',
                    sql_name='date_to',
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.contract_type,
                    enum=ContractType,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.car_supplier,
                    sql_name='supplier',
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.financial_rent_tax_exc,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.maintenance_rent_tax_exc,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.tires_rent_tax_exc,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.financial_loss_rent_tax_exc,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.replacement_vehicle_rent_tax_exc,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.relay_vehicle_rent_tax_exc,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.insurance_rent_tax_exc,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.fuel_card_management_rent_tax_exc,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.management_fee_rent_tax_exc,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.assistance_rent_tax_exc,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.telematics_rent_tax_exc,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.other_rent_tax_exc,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.total_rent_tax_exc,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.tires_contract_nb,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.restitution_date,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.interest_rate,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.residual_value,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.resale_price,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.resale_date,
                ),
                InputColumn.from_data_column(
                    column=SoonGoRecordsModel.connector_name,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=SoonGoRecordsModel.synchronisation_type,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=SoonGoRecordsModel.synchronisation_id,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=SoonGoRecordsModel.file_creation_date,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=VehicleContractsModel.sync_key,
                    nullable=False,
                    sliding_col='update',
                )
            ],
        )

    def _get_df(
        self: typing.Self,
        connector_data: ConnectorData,
        logger: logging.Logger,
        fetch_params_dict: typing.Optional[dict] = None,
    ) -> pd.DataFrame:
        """ Get vehicle table for Go Measure inputting

        :param gac_data: GacData with all data imported from gac

        :return: pandas dataframe with all columns from the vehicle table
        """
        # Get rental data
        combined_df = self.fetch_table_data(
            connector_data=connector_data,
            logger=logger,
            fetch_params_dict=fetch_params_dict,
        )
        combined_df = add_synchronization_id(combined_df, connector_data)
        if combined_df.empty:
            return combined_df

        # Deduplicate
        org_associations_params = fetch_organization_params(
            connector_data.organization_name
        )[self.name]
        if org_associations_params.get('deduplicate'):
            combined_df = self.deduplicate_contracts(
                combined_df=combined_df,
                logger=logger,
            )

        combined_df = self.get_tax_exc_rent_cols(
            rent_df=combined_df,
            connector_data=connector_data,
            logger=logger,
        )
        combined_df = self.get_tires_cols(
            combined_df=combined_df,
        )

        combined_df[VehicleContractsModel.sync_key.name] = self.compute_sync_key(
            data_df=combined_df,
        )

        combined_df = self.fill_missing_cols(df=combined_df)

        # Lease start date does not change across amendments
        combined_df[VehicleContractsModel.lease_start_date.name] = (
            combined_df[VehicleContractsModel.lease_start_date.name].fillna(
                combined_df.groupby(
                    VehiclesModel.plate_number.name,
                )[VehicleContractsModel.lease_start_date.name].min()
            )
        )

        return combined_df.loc[
            ~str_is_nan(combined_df[VehiclesModel.plate_number.name]),
            self.return_column_names()
        ]

    def get_tax_exc_rent_cols(
        self: typing.Self,
        rent_df: pd.DataFrame,
        logger: logging.Logger,
        connector_data: ConnectorData,
    ) -> pd.DataFrame:
        """ Get net rent columns from rent_df

        :param rent_df: DataFrame with rent columns

        :returns: DataFrame with net rent columns deducted from tax_exc and ttc rent
        """
        if VehiclesModel.fiscal_type.name not in rent_df.columns:
            rent_df = fetch_vehicle_data(
                df=rent_df,
                cols_to_fetch={VehiclesModel.fiscal_type.name, },
                connector_data=connector_data,
                logger=logger,
            )
        assert VehiclesModel.fiscal_type.name in rent_df.columns, 'Fiscal type required'
        net_to_tax_exc_ratio = rent_df[VehiclesModel.fiscal_type.name].map(
            {
                FiscalType.personal_car.value: 1/1.2,
                FiscalType.two_wheel.value: 1/1.2,
                FiscalType.utility_car.value: 1,
                FiscalType.other.value: 1,
            }
        ).fillna(1.2)   # In the absence of information assume personal
        ttc_to_tax_exc_ratio = 1/1.2

        # Fill in other category
        other_col_tax_exc = {
            VehicleContractsModel.accident_management_rent_tax_exc.name,
            VehicleContractsModel.vignette_rent_tax_exc.name,
            VehicleContractsModel.service_fees_rent_tax_exc.name,
        }.intersection(rent_df.columns)
        if (
            (VehicleContractsModel.other_rent_tax_exc.name in rent_df.columns)
            and other_col_tax_exc
        ):
            rent_df[VehicleContractsModel.other_rent_tax_exc.name] = (
                rent_df[VehicleContractsModel.other_rent_tax_exc.name].mask(
                    ~series_is_nan(rent_df[VehicleContractsModel.other_rent_tax_exc.name]),
                    rent_df[VehicleContractsModel.other_rent_tax_exc.name] +
                    rent_df[list(other_col_tax_exc)].fillna(0).sum(axis=1)
                )
            )

        other_col_ttc = {
            VehicleContractsModel.accident_management_rent_ttc.name,
            VehicleContractsModel.vignette_rent_ttc.name,
            VehicleContractsModel.service_fees_rent_ttc.name,
        }.intersection(rent_df.columns)
        if (
            (VehicleContractsModel.other_rent_ttc.name in rent_df.columns)
            and other_col_ttc
        ):
            rent_df[VehicleContractsModel.other_rent_ttc.name] = (
                rent_df[VehicleContractsModel.other_rent_ttc.name].mask(
                    ~series_is_nan(rent_df[VehicleContractsModel.other_rent_ttc.name]),
                    rent_df[VehicleContractsModel.other_rent_ttc.name] +
                    rent_df[list(other_col_ttc)].fillna(0).sum(axis=1)
                )
            )

        other_col_net = {
            VehicleContractsModel.accident_management_rent_net.name,
            VehicleContractsModel.vignette_rent_net.name,
            VehicleContractsModel.service_fees_rent_net.name,
        }.intersection(rent_df.columns)
        if (
            (VehicleContractsModel.other_rent_net.name in rent_df.columns)
            and other_col_net
        ):
            rent_df[VehicleContractsModel.other_rent_net.name] = (
                rent_df[VehicleContractsModel.other_rent_net.name].mask(
                    ~series_is_nan(rent_df[VehicleContractsModel.other_rent_net.name]),
                    rent_df[VehicleContractsModel.other_rent_net.name] +
                    rent_df[list(other_col_net)].fillna(0).sum(axis=1)
                )
            )

        for ttc_col in [
            VehicleContractsModel.financial_rent_ttc.name,
            VehicleContractsModel.maintenance_rent_ttc.name,
            VehicleContractsModel.tires_rent_ttc.name,
            VehicleContractsModel.financial_loss_rent_ttc.name,
            VehicleContractsModel.replacement_vehicle_rent_ttc.name,
            VehicleContractsModel.relay_vehicle_rent_ttc.name,
            VehicleContractsModel.insurance_rent_ttc.name,
            VehicleContractsModel.fuel_card_management_rent_ttc.name,
            VehicleContractsModel.management_fee_rent_ttc.name,
            VehicleContractsModel.assistance_rent_ttc.name,
            VehicleContractsModel.telematics_rent_ttc.name,
            VehicleContractsModel.other_rent_ttc.name,
            VehicleContractsModel.accident_management_rent_ttc.name,
            VehicleContractsModel.vignette_rent_ttc.name,
            VehicleContractsModel.service_fees_rent_ttc.name,
            VehicleContractsModel.total_rent_ttc.name,
        ]:
            if ttc_col in rent_df.columns:
                tax_exc_col = ttc_col[:-3] + 'tax_exc'
                inferred_value = rent_df[ttc_col] * ttc_to_tax_exc_ratio
                if tax_exc_col not in rent_df.columns:
                    rent_df[tax_exc_col] = inferred_value
                else:
                    rent_df[tax_exc_col] = rent_df[tax_exc_col].fillna(inferred_value)

        for net_col in [
            VehicleContractsModel.financial_rent_net.name,
            VehicleContractsModel.maintenance_rent_net.name,
            VehicleContractsModel.tires_rent_net.name,
            VehicleContractsModel.financial_loss_rent_net.name,
            VehicleContractsModel.replacement_vehicle_rent_net.name,
            VehicleContractsModel.relay_vehicle_rent_net.name,
            VehicleContractsModel.insurance_rent_net.name,
            VehicleContractsModel.fuel_card_management_rent_net.name,
            VehicleContractsModel.management_fee_rent_net.name,
            VehicleContractsModel.assistance_rent_net.name,
            VehicleContractsModel.telematics_rent_net.name,
            VehicleContractsModel.other_rent_net.name,
            VehicleContractsModel.accident_management_rent_net.name,
            VehicleContractsModel.vignette_rent_net.name,
            VehicleContractsModel.service_fees_rent_net.name,
            VehicleContractsModel.total_rent_net.name,
        ]:
            if net_col in rent_df.columns:
                tax_exc_col = net_col[:-3] + 'tax_exc'
                inferred_value = rent_df[net_col] * net_to_tax_exc_ratio
                if tax_exc_col not in rent_df.columns:
                    rent_df[tax_exc_col] = inferred_value
                else:
                    rent_df[tax_exc_col] = rent_df[tax_exc_col].fillna(inferred_value)

        # Fill in total_rent
        rent_cols = {
            VehicleContractsModel.financial_rent_tax_exc.name,
            VehicleContractsModel.maintenance_rent_tax_exc.name,
            VehicleContractsModel.tires_rent_tax_exc.name,
            VehicleContractsModel.financial_loss_rent_tax_exc.name,
            VehicleContractsModel.replacement_vehicle_rent_tax_exc.name,
            VehicleContractsModel.relay_vehicle_rent_tax_exc.name,
            VehicleContractsModel.insurance_rent_tax_exc.name,
            VehicleContractsModel.fuel_card_management_rent_tax_exc.name,
            VehicleContractsModel.management_fee_rent_tax_exc.name,
            VehicleContractsModel.assistance_rent_tax_exc.name,
            VehicleContractsModel.telematics_rent_tax_exc.name,
            VehicleContractsModel.other_rent_tax_exc.name,
        }.intersection(rent_df.columns)
        rent_df[VehicleContractsModel.total_rent_tax_exc.name] = (
            rent_df[list(rent_cols)].fillna(0).sum(axis=1)
        )

        return rent_df

    def get_tires_cols(
        self: typing.Self,
        combined_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """ Get tires columns from tires_df

        :param tires_df: DataFrame with tires columns

        :returns: DataFrame with tires columns
        """
        tires_cols = {
            VehicleContractsModel.summer_tires_contract_nb.name,
            VehicleContractsModel.winter_tires_contract_nb.name,
        }.intersection(combined_df.columns)
        if tires_cols:
            combined_tires_nb = combined_df[
                list(tires_cols)
            ].fillna(0).sum(axis=1)
            combined_tires_nb = combined_tires_nb.mask(
                combined_tires_nb == 0,
                np.nan,
            )

            if (
                VehicleContractsModel.tires_contract_nb.name not in combined_df.columns
            ):
                combined_df[VehicleContractsModel.tires_contract_nb.name] = (
                    combined_tires_nb
                ).astype('Int64')
            else:
                combined_df[VehicleContractsModel.tires_contract_nb.name] = (
                    combined_df[VehicleContractsModel.tires_contract_nb.name].fillna(
                        combined_tires_nb
                    )
                ).astype('Int64')

        if VehicleContractsModel.tires_contract_nb.name in combined_df.columns:
            combined_df[VehicleContractsModel.tires_contract_nb.name] = (
                combined_df[VehicleContractsModel.tires_contract_nb.name]
            ).astype('Int64')

        return combined_df

    def deduplicate_contracts(
        self: typing.Self,
        combined_df: pd.DataFrame,
        logger: logging.Logger,
    ) -> pd.DataFrame:
        """ Deduplicate contracts dataframe. For the moment do not handle
        multiple contracts for the same vehicle

        :param combined_df: DataFrame with licence_plate duplicates
        :param logger: logger

        :returns: deduplicated DataFrame
        """
        combined_df = combined_df[
            ~str_is_nan(combined_df[VehiclesModel.plate_number.name])
        ]

        dedup_df = combined_df[[VehiclesModel.plate_number.name]].drop_duplicates()

        if VehiclesModel.car_supplier.name not in combined_df.columns:
            combined_df[VehiclesModel.car_supplier.name] = np.nan
        combined_df['is_supplier'] = (
            combined_df[VehiclesModel.car_supplier.name] == 
            combined_df[SoonGoRecordsModel.connector_name.name].mask(
                combined_df[SoonGoRecordsModel.connector_name.name] == 'LOC_ACTION',
                'LEASEPLAN'
            )
        )
        initial_plate_set = set(dedup_df[VehiclesModel.plate_number.name])
        record_col = SoonGoRecordsModel.record_date.name
        zero_date = datetime(year=1900, month=1, day=1)

        for col_name in [
            col for col in combined_df.columns
            if col not in (record_col, 'is_supplier', VehiclesModel.plate_number.name)
        ]:

            if (
                col_name not in combined_df.columns or
                col_name == VehiclesModel.plate_number.name
            ):
                continue

            # Identify non nan values
            data_cols = [
                VehiclesModel.plate_number.name,
                col_name,
                record_col,
                'is_supplier',
            ]
            subset_df = combined_df.loc[
                ~series_is_nan(combined_df[col_name]),
                data_cols,
            ].drop_duplicates(data_cols)

            # Deduplicate, keep only most recent records. Consider nan records as 0
            subset_df[record_col] = subset_df[record_col].fillna(zero_date)
            subset_df = keep_duplicates(
                duplicated_df=subset_df,
                unique_cols=[VehiclesModel.plate_number.name],
                selection_col=record_col,
                logger=logger,
            )

            # For connector_name, dataset, and type, keep any
            if col_name in (
                SoonGoRecordsModel.connector_name.name,
                SoonGoRecordsModel.synchronisation_type.name,
                SoonGoRecordsModel.synchronisation_id.name,
            ):
                subset_df = subset_df.drop_duplicates(
                    subset=[
                        col for col in subset_df.columns
                        if col not in [col_name, 'is_supplier']
                    ]
                )

            # For contract reference, prefer the reference from the car_supplier
            # otherwise keep any
            if col_name == VehicleContractsModel.contract_reference.name:
                subset_df = keep_duplicates(
                    duplicated_df=subset_df[data_cols],
                    unique_cols=[VehiclesModel.plate_number.name],
                    selection_col='is_supplier',
                    logger=logger,
                    selection_func='max',
                )
                subset_df = subset_df.drop_duplicates(
                    subset=[col for col in subset_df.columns if col != col_name]
                )

            dup_plates = subset_df[VehiclesModel.plate_number.name].duplicated(
                keep=False,
            )
            if dup_plates.any():
                logger.error(
                    f'Duplicated values for {col_name}: '
                    f'{subset_df[VehiclesModel.plate_number.name].loc[dup_plates]}'
                )
                subset_df = subset_df.loc[~dup_plates]  # Turns duplicated values into nan

            # Merge deduplicated column back into deduplicated df
            dedup_df = dedup_df.merge(
                right=subset_df[[VehiclesModel.plate_number.name, col_name]],
                on=VehiclesModel.plate_number.name,
                how='outer',
                indicator=True,
                validate='1:1',
            )
            assert dedup_df['_merge'].isin(['left_only', 'both']).all()
            dedup_df.drop('_merge', axis=1, inplace=True)

        assert dedup_df[VehiclesModel.plate_number.name].is_unique

        final_plate_set = set(dedup_df[VehiclesModel.plate_number.name])
        assert final_plate_set == initial_plate_set
        return dedup_df

    def compute_sync_key(
        self: typing.Self,
        data_df: pd.DataFrame,
    ) -> pd.Series:
        """ Compute the sync key for the vehicle table

        :param data_df: DataFrame with all columns from the vehicle table

        :returns: Series with the sync key
        """
        sync_key = pd.Series('', index=data_df.index)
        for col in (
            VehicleContractsModel.lease_mileage,
            VehicleContractsModel.lease_months,
            VehicleContractsModel.lease_start_date,
            VehicleContractsModel.lease_end_date,
            VehicleContractsModel.total_rent_tax_exc,
        ):
            if col.name not in data_df.columns:
                data_df[col.name] = get_dtype_null(col.dtype)

            if pd.api.types.is_datetime64_any_dtype(data_df[col.name]):
                data_value = data_df[col.name].dt.strftime(r'%Y-%m-%d').fillna('-')
            elif pd.api.types.is_numeric_dtype(data_df[col.name]):
                data_value = data_df[col.name].round(2).astype(str).fillna('-')
            else:
                data_value = data_df[col.name].astype(str).fillna('-')

            sync_key += f'{col.name}:' + data_value + '|'

        return sync_key.str[:-1]  # Remove last '|'

    def to_sql(
        self: typing.Self,
        data_df: pd.DataFrame,
        organization_id: str,
        session: sa.orm.Session,
        logger: logging.Logger,
        update_values: str = 'null_only',
        columns: typing.List[str] = None,
    ) -> None:
        """ Push new services to the database

        :param connector_data: connector Data Class with all folders
        """
        data_df.reset_index(drop=True, inplace=True)
        db_df = pd.read_sql(
            sa.text(
                """
                WITH vehicle_contracts_ranked AS (
                    select
                        vehicle_contracts.*,
                        row_number() over (
                            partition by vehicle_id
                            order by
                                date_from desc nulls last,
                                coalesce(date_to, now()) desc,
                                id -- tie breaker
                        ) as contracts_rank
                    from publ.vehicle_contracts
                )
                    SELECT
                        vehicles.plate_number,
                        vehicle_contracts_ranked.id,
                        vehicle_contracts_ranked.lease_mileage as previous_lease_mileage,
                        vehicle_contracts_ranked.lease_months as previous_lease_months,
                        vehicle_contracts_ranked.lease_start_date as previous_lease_start_date,
                        vehicle_contracts_ranked.lease_end_date as previous_lease_end_date,
                        vehicle_contracts_ranked.total_rent_tax_exc as previous_total_rent_tax_exc,
                        vehicle_contracts_ranked.sync_key as previous_sync_key,
                        vehicle_contracts_ranked.date_from as previous_date_from
                    FROM vehicle_contracts_ranked
                    INNER join publ.vehicles
                        on vehicles.id = vehicle_contracts_ranked.vehicle_id
                    where vehicles.organization_id = :organization_id
                        and vehicle_contracts_ranked.contracts_rank = 1
                """
            ),
            session.bind,
            params={'organization_id': organization_id},
        )

        joined_df = data_df.merge(
            right=db_df,
            on=VehiclesModel.plate_number.name,
            how='left',
            indicator=True,
            validate='1:1',
        )
        assert joined_df['_merge'].isin(['left_only', 'both']).all()
        joined_df.drop('_merge', axis=1, inplace=True)

        insert_df = data_df[
            str_is_nan(joined_df['id'])
        ]
        insert_df[VehicleContractsModel.contract_start_date.name] = (
            insert_df[VehicleContractsModel.contract_start_date.name].fillna(
                insert_df[VehicleContractsModel.lease_start_date.name]
            )
        )
        super().to_sql(
            data_df=insert_df,
            organization_id=organization_id,
            session=session,
            logger=logger,
            update_values=update_values,
            columns=columns,
        )

        # Filter updates
        if not db_df.empty:
            update_params = session.execute(
                sa.select(
                    OrganizationParametersTable.value
                ).where(
                    OrganizationParametersTable.organization_id == organization_id,
                    OrganizationParametersTable.name == 'contract_tolerance'
                )
            ).scalar()
            update_params = DEFAULT_VALIDATION_PARAMS | (update_params or {})
            organization_tz = session.execute(
                sa.select(
                    OrganizationParametersTable.value['value']
                ).where(
                    OrganizationParametersTable.organization_id == organization_id,
                    OrganizationParametersTable.name == 'default_timezone'
                )
            ).scalar()
            organization_tz = organization_tz or 'Europe/Paris'
            is_change = self.compute_is_change(
                joined_df,  # Need the previous values
                org_tz=organization_tz,
                **update_params,
            )
            if not pd.api.types.is_datetime64_any_dtype(joined_df['previous_date_from'].dtype):
                joined_df['previous_date_from'] = pd.to_datetime(
                    joined_df['previous_date_from']
                )
            else:
                joined_df['previous_date_from'] = (
                    joined_df['previous_date_from'].dt.tz_convert(organization_tz)
                ).dt.tz_localize(None)
            new_amendments_df = joined_df[
                is_change &
                (joined_df['previous_date_from'] <= joined_df[VehicleContractsModel.contract_start_date.name].fillna(pd.Timestamp.now()))
            ]
            if new_amendments_df[SoonGoRecordsModel.file_creation_date.name].dt.tz is not None:
                new_amendments_df[SoonGoRecordsModel.file_creation_date.name] = (
                    new_amendments_df[SoonGoRecordsModel.file_creation_date.name].dt.tz_convert(
                        organization_tz
                    ).dt.tz_localize(None)
                )
            new_amendments_df[VehicleContractsModel.contract_start_date.name] = (
                new_amendments_df[VehicleContractsModel.contract_start_date.name].fillna(
                    # We use the date of insert into db as a second best
                    new_amendments_df[
                        [
                            SoonGoRecordsModel.file_creation_date.name,
                            'previous_date_from'
                        ]
                    ].max(axis=1)
                )
            )
            incoherent_contract_dates = (
                new_amendments_df[VehicleContractsModel.contract_start_date.name] <=
                new_amendments_df[VehicleContractsModel.contract_end_date.name]
            )
            if incoherent_contract_dates.any():
                logger.error(
                    '%d incoherent contract dates found in vehicle contracts: ',
                    incoherent_contract_dates.sum()
                )
            new_amendments_df = new_amendments_df.loc[
                ~incoherent_contract_dates,
                data_df.columns
            ]
            super().to_sql(
                data_df=new_amendments_df,
                organization_id=organization_id,
                session=session,
                logger=logger,
                update_values=update_values,
                columns=columns,
            )

    @staticmethod
    def compute_is_change(
        data_df: pd.DataFrame,
        org_tz: str = 'Europe/Paris',
        **validation_params,
    ):
        """ Compute is_change column if the change in contracts is large enough

        :param data_df: DataFrame with all columns from the vehicle contracts table

        :returns: Series with the is_change column
        """
        is_change = pd.Series(False, index=data_df.index)
        for col, tolerance in validation_params.items():
            if pd.api.types.is_datetime64_any_dtype(data_df[col]):
                data_df[f'previous_{col}'] = pd.to_datetime(data_df[f'previous_{col}'])
                if data_df[f'previous_{col}'].dt.tz is not None:
                    data_df[f'previous_{col}'] = data_df[f'previous_{col}'].dt.tz_convert(
                        org_tz
                    )
                    data_df[f'previous_{col}'] = data_df[f'previous_{col}'].dt.tz_localize(
                        None,
                    )

                days_diff = (
                    data_df[col] - data_df[f'previous_{col}']
                ).dt.total_seconds() / (24 * 60 * 60)
                is_change |= (
                    (days_diff.abs() > tolerance)
                    |
                    (
                        data_df[f'previous_{col}'].isna() & 
                        data_df[col].notna()
                    )
                )

            elif pd.api.types.is_numeric_dtype(data_df[col]):
                diff = data_df[col] - data_df[f'previous_{col}']
                is_change |= (
                    (diff.abs() > tolerance)
                    |
                    (
                        data_df[f'previous_{col}'].isna() & 
                        data_df[col].notna()
                    )
                )
            else:
                is_change |= (
                    (data_df[col] != data_df[f'previous_{col}'])
                    |
                    (
                        data_df[f'previous_{col}'].isna() &
                        data_df[col].notna()
                    )
                )
            pass

        return is_change


if __name__ == "__main__":
    logger = gen_logger('vehicle_contract_table')
    organization_name = 'udaf'
    root_folder = os.environ['_soongo_data_folder']
    organization_folder = os.path.join(
        root_folder,
        organization_name,
    )
    connector_data = ConnectorData(
        root_folder=root_folder,
        organization_name=organization_name,
    )
    vehicle_contract_table = VehicleContractsInputTable()
    contract_df = vehicle_contract_table.get(
        connector_data=connector_data,
        logger=logger,
    )

    vehicle_contract_table.check_columns(
        data_df=contract_df,
        logger=logger,
    )

    contract_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{vehicle_contract_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
