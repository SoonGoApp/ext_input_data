""" Script to calculate the vehicle table on which to compute impacts."""
import logging
import os
import typing

import numpy as np
import pandas as pd
import sqlalchemy as sa

from soongo_data.connectors import ConnectorData
from soongo_data.connectors.greenncap.full_data import GreenNCapConnector
from soongo_data.data_models import (BusinessUnitsModel, MileageReportsModel,
                                     SoonGoRecordsModel,
                                     VehicleAssociationsModel,
                                     VehicleOrdersModel, VehiclesModel,
                                     VehicleStatusModel)
from soongo_data.sql_mappings import VehiclesTable
from soongo_data.utils.enums import (FiscalType, Makes, ModelCategories,
                                     Models, ModelVersions, mapper_factory)
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id,
                                            keep_duplicates)
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.type import series_is_nan, str_is_nan, get_dtype_null

pd.set_option('future.no_silent_downcasting', True)


@add_input_table
class VehiclesInputTable(InputTable):

    def __init__(self):
        super().__init__(
            sql_mapping=VehiclesTable,
            columns=[
                InputColumn.from_data_column(
                    column=VehiclesModel.plate_number,
                    nullable=False,
                    unique=True,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.make,
                    enum=Makes,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.model,
                    enum=Models,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.full_model,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.co2_per_km,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.co2_production,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.co2_recycling,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.energy,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.manufacturer_price_tax_exc,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.rebate_rate,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.rebate_price,
                ),
                InputColumn.from_data_column(
                    column=VehicleOrdersModel.order_reference,
                ),
                InputColumn.from_data_column(
                    column=VehicleStatusModel.vehicle_status,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.vehicle_age,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.initial_mileage,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.fiscal_power,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.fiscal_type,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.is_air_quality_certified,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.seat_count,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.theoretical_fuel_consumption,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.entry_into_service_date,
                ),
                InputColumn.from_data_column(
                    column=VehicleAssociationsModel.assignment_type,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.model_category,
                    enum=ModelCategories,
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
                    column=VehiclesModel.entry_into_fleet_date,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.exit_from_fleet_date,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.model_version,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.vehicle_external_colour,
                    sql_name='color',
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.door_count,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.electricity_consumption,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.battery_capacity,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.battery_price_tax_inc,
                    sql_name='battery_price',
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.max_elec_recharge,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.transmission_type,
                    sql_name='transmission',
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.air_quality_certificate_level,
                    sql_name='critair',
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.curb_weight,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.vehicle_empty_weight,
                    sql_name='empty_weight',
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.motor_power,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.fuel_tank_capacity,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.registration_type,
                    sql_name='national_type',
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.vin,
                ),
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

        if VehiclesModel.model.name in combined_df.columns:
            combined_df[VehiclesModel.model_category.name] = (
                mapper_factory(ModelCategories)(
                    combined_df[VehiclesModel.model.name]
                )
            )
            assert (
                str_is_nan(combined_df[VehiclesModel.model_category.name]) ==
                str_is_nan(combined_df[VehiclesModel.model.name])
            ).all(), 'Some models are missing a model_category'
            combined_df[VehiclesModel.model_version.name] = self.get_model_version(
                vehicle_df=combined_df,
            )
        else:
            combined_df[VehiclesModel.model.name] = ''

        # Deduplicate
        combined_df = self.deduplicate_vehicule(
            combined_df=combined_df,
            logger=logger,
        )

        if VehiclesModel.model_category.name in combined_df.columns:
            combined_df[VehiclesModel.fiscal_type.name] = self.get_fiscal_type(
                vehicle_df=combined_df,
            )

        greenncap_connector = GreenNCapConnector(
            folder=connector_data.root_folder,
            organization_name=connector_data.organization_name,
            log_file=connector_data.log_file,
            s3_bucket=connector_data.s3_bucket,
        )
        combined_df = self.add_co2_data(
            logger=logger,
            vehicle_df=combined_df,
            co2_df=greenncap_connector.get(
                'GREENNCAP',
            ).get(
                'CARBON_PER_MODEL',
            ),
        )
        combined_df = self.fill_missing_cols(df=combined_df)

        return combined_df[self.return_column_names()]

    @staticmethod
    def add_co2_data(
        vehicle_df: pd.DataFrame,
        co2_df: pd.DataFrame,
        logger: logging.Logger,
    ):
        """ Complete missing CO2 information in the vehicle dataframe

        :param vehicle_df: the vehicle dataframe to complete
        :param co2_df: a source of CO2 information
        """
        co2_df = co2_df[
            [
                VehiclesModel.model.name,
                VehiclesModel.energy.name,
                VehiclesModel.co2_production.name,
                VehiclesModel.co2_recycling.name,
            ]
        ]
        co2_cols = [
            VehiclesModel.co2_production,
            VehiclesModel.co2_recycling,
        ]
        for col in co2_cols:
            # Convert all to kg
            if col.post_processing:
                co2_df[col.name] = col.post_processing(co2_df[col.name])

        co2_df = co2_df.groupby(
            [VehiclesModel.model.name, VehiclesModel.energy.name]
        ).mean().reset_index()

        lacking_cols = {VehiclesModel.model.name, VehiclesModel.energy.name}.difference(
            set(vehicle_df.columns)
        )
        for col in lacking_cols:
            vehicle_df[col] = ''

        vehicle_df = vehicle_df.merge(
            right=co2_df,
            on=[VehiclesModel.model.name, VehiclesModel.energy.name],
            how='left',
            validate='m:1',
            indicator=True,
        )
        logger.info(
            '%d vehicles footprint could be found in CO2 data out of %d vehicles',
            (vehicle_df['_merge'] == 'both').sum(),
            len(vehicle_df),
        )

        return vehicle_df

    @staticmethod
    def get_fiscal_type(vehicle_df: pd.DataFrame) -> pd.Series:
        """ Get fiscal type

        :param vehicle_df: vehicle dataframe

        :returns: fiscal type
        """
        if VehiclesModel.fiscal_type.name not in vehicle_df.columns:
            vehicle_df[VehiclesModel.fiscal_type.name] = ''
        if VehiclesModel.model_category.name not in vehicle_df.columns:
            raise ValueError(
                'Cannot compute fiscal type without model_category column'
            )

        fiscal_type_map = {
            ModelCategories.utility.value: FiscalType.utility_car.value,
            ModelCategories.two_wheel.value: FiscalType.two_wheel.value,
            ModelCategories.truck.value: FiscalType.utility_car.value,
            ModelCategories.unknown.value: FiscalType.other.value,
        }
        mapped_values = vehicle_df[VehiclesModel.model_category.name].map(
            fiscal_type_map
        )
        assert (
            str_is_nan(mapped_values) ==
            ~(vehicle_df[VehiclesModel.model_category.name].isin(fiscal_type_map.keys()))
        ).all(), 'Some model categories not mapped despite being available in fiscal_type_map'

        vehicle_df[VehiclesModel.fiscal_type.name] = vehicle_df[VehiclesModel.fiscal_type.name].mask(
            ~str_is_nan(mapped_values),
            mapped_values,
        )
        return vehicle_df[VehiclesModel.fiscal_type.name]

    @staticmethod
    def get_model_version(vehicle_df: pd.DataFrame) -> pd.Series:
        """ Get full model version

        :param vehicle_df: vehicle dataframe

        :returns: full model version
        """
        vehicle_df[VehiclesModel.model_version.name] = ''
        if VehiclesModel.full_model.name not in vehicle_df.columns:
            return vehicle_df[VehiclesModel.model_version.name]

        for model_version in ModelVersions:
            version_update = (
                (vehicle_df[VehiclesModel.model.name] == model_version.value.model.value)
                &
                vehicle_df[VehiclesModel.full_model.name].str.contains(
                    model_version.value.version_regex
                )
            )
            if not str_is_nan(vehicle_df.loc[version_update, VehiclesModel.model_version.name]).all():
                raise ValueError(
                    f'Multiple versions for model '
                    f'{model_version.value.model.value} and full_model '
                    f'{vehicle_df.loc[version_update, VehiclesModel.full_model.name]}'
                )
            vehicle_df.loc[version_update, VehiclesModel.model_version.name] = (
                model_version.value.name
            )
        return vehicle_df[VehiclesModel.model_version.name]

    def deduplicate_vehicule(
        self: typing.Self,
        combined_df: pd.DataFrame,
        logger: logging.Logger,
    ) -> pd.DataFrame:
        """ Deduplicate vehicule dataframe

        :param combined_df: DataFrame with licence_plate duplicates
        :param logger: logger

        :returns: deduplicated DataFrame
        """
        combined_df = combined_df[
            ~str_is_nan(combined_df[VehiclesModel.plate_number.name])
        ]
        if VehiclesModel.initial_mileage.name not in combined_df.columns:
            combined_df[VehiclesModel.initial_mileage.name] = 0

        dedup_df = combined_df[[VehiclesModel.plate_number.name]].drop_duplicates()
        initial_plate_set = set(dedup_df[VehiclesModel.plate_number.name])
        record_col = SoonGoRecordsModel.record_date.name
        zero_date = pd.Timestamp(year=1900, month=1, day=1)

        for col_name in self.return_column_names():

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
            ]
            if col_name == 'rebate_price':
                combined_df['reliable_source'] = np.where(
                    combined_df[SoonGoRecordsModel.connector_name.name] == 'FLEETNOTE',
                    0,
                    1,
                )
                data_cols.append('reliable_source')
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

            # For BU or status if clash then replace with null (unknown)
            if col_name in [
                BusinessUnitsModel.business_unit.name,
                VehiclesModel.vehicle_status.name,
                VehiclesModel.full_model.name,
                VehicleAssociationsModel.assignment_type.name,
                VehiclesModel.model.name,
                VehiclesModel.make.name,
                VehiclesModel.model_category.name,
                VehiclesModel.energy.name,
                VehiclesModel.is_air_quality_certified.name,
                VehiclesModel.rebate_price.name,
                VehiclesModel.vin.name,
            ]:
                subset_df['dup_count'] = subset_df.groupby(
                    VehiclesModel.plate_number.name
                )[VehiclesModel.plate_number.name].transform('count')
                subset_df[col_name] = (
                    subset_df[col_name].mask(
                        subset_df['dup_count'] > 1,
                        get_dtype_null(subset_df[col_name].dtype)
                    )
                )
                subset_df = subset_df.drop('dup_count', axis=1)
                subset_df = subset_df.drop_duplicates()

            # For mileage, possible multiple values for same day. Keep largest.
            mileage_cols = [
                VehiclesModel.initial_mileage.name,
            ]
            if col_name in mileage_cols:
                subset_df = keep_duplicates(
                    duplicated_df=subset_df[data_cols],
                    unique_cols=[VehiclesModel.plate_number.name],
                    selection_col=col_name,
                    logger=logger,
                )

            # For entry_into_service date or lease_start_date, keep earliest.
            if col_name in (
                VehiclesModel.entry_into_service_date.name,
                VehiclesModel.entry_into_fleet_date.name,
            ):
                subset_df = keep_duplicates(
                    duplicated_df=subset_df[data_cols],
                    unique_cols=[VehiclesModel.plate_number.name],
                    selection_col=col_name,
                    logger=logger,
                    selection_func='min',
                )

            # For end dates, keep latest.
            if col_name in (
                VehiclesModel.exit_from_fleet_date.name,
            ):
                subset_df = keep_duplicates(
                    duplicated_df=subset_df[data_cols],
                    unique_cols=[VehiclesModel.plate_number.name],
                    selection_col=col_name,
                    logger=logger,
                    selection_func='max',
                )

            # For rebate_price, keep from reliable sources in priority
            if col_name in (
                VehiclesModel.rebate_price.name,
            ):
                subset_df = keep_duplicates(
                    duplicated_df=subset_df[data_cols],
                    unique_cols=[VehiclesModel.plate_number.name],
                    selection_col='reliable_source',
                    logger=logger,
                    selection_func='max',
                )

            # For connector_name, dataset, and type, keep any
            if col_name in (
                SoonGoRecordsModel.connector_name.name,
                SoonGoRecordsModel.synchronisation_type.name,
                SoonGoRecordsModel.synchronisation_id.name,
            ):
                subset_df = subset_df.drop_duplicates(
                    subset=[col for col in subset_df.columns if col != col_name]
                )

            dup_plates = subset_df[VehiclesModel.plate_number.name].duplicated(
                keep=False,
            )
            if dup_plates.any():
                raise ValueError(
                    f'Duplicated values for {col_name}: '
                    f'{subset_df[VehiclesModel.plate_number.name].loc[dup_plates]}'
                )

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

    def to_sql(
        self: typing.Self,
        data_df: pd.DataFrame,
        organization_id: str,
        session: sa.orm.Session,
        logger: logging.Logger,
        update_values: str = 'null_only',
        columns: typing.Optional[typing.List[str]] = None,
    ) -> None:
        if (update_values in ('overwrite', 'inc_null')) and (
            (columns is None)
        ):
            # Because many modifications happen in app we cannot modify status
            logger.warning(
                'Vehicles table exit_from_fleet_date cannot be overwritten '
                'modifying columns argument to all but exit_from_fleet_date. '
                'pass exit_from_fleet_date explicitely if you want to change it'
            )
            columns = [
                col.sql_name for col in self.columns
                if col != VehiclesModel.exit_from_fleet_date.name
            ]

        super().to_sql(
            data_df,
            organization_id,
            session,
            logger,
            update_values,
            columns,
        )

        session.execute(
            sa.text('refresh materialized view concurrently publ.vehicles_view;')  # vehicles_view"
        )


if __name__ == "__main__":
    logger = gen_logger('vehicle_table')
    organization_name = 'quartus'
    root_folder = os.environ['_soongo_data_folder']
    organization_folder = os.path.join(
        root_folder,
        organization_name,
    )
    connector_data = ConnectorData(
        root_folder=root_folder,
        organization_name=organization_name,
    )
    vehicle_table = VehiclesInputTable()
    vehicle_df = vehicle_table.get(
        connector_data=connector_data,
        logger=logger,
    )

    vehicle_table.check_columns(
        data_df=vehicle_df,
        logger=logger,
    )

    vehicle_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{vehicle_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
