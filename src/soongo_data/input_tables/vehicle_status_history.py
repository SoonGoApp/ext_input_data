""" Script to calculate the vehicle table on which to compute impacts."""
import logging
import os
import typing
from datetime import datetime

import pandas as pd
from sqlalchemy import UUID
from sqlalchemy.orm import Session

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (SoonGoRecordsModel, VehiclesModel,
                                     VehicleStatusModel)
from soongo_data.sql_mappings import VehicleStatusHistoryTable
from soongo_data.utils.enums import VehicleStatus
from soongo_data.utils.fetch import fetch_vehicle_data
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id)
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.type import series_is_nan

pd.set_option('future.no_silent_downcasting', True)


@add_input_table
class VehiclesStatusInputTable(InputTable):

    def __init__(self):
        super().__init__(
            sql_mapping=VehicleStatusHistoryTable,
            columns=[
                InputColumn.from_data_column(
                    column=VehiclesModel.vehicle_status,
                    nullable=False,
                    enum=VehicleStatus,
                    sliding_col='update',
                    sql_name='status',
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.plate_number,
                    nullable=False,
                    unique=True,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=VehicleStatusModel.vehicle_status_start_date,
                    sliding_col='start',
                    sql_name='date_from',
                ),
                InputColumn.from_data_column(
                    column=VehicleStatusModel.vehicle_status_end_date,
                    sliding_col='end',
                    sql_name='date_to',
                ),
                InputColumn.from_data_column(
                    column=VehicleStatusModel.reason,
                ),
                InputColumn.from_data_column(
                    column=VehicleStatusModel.created_by,
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
            ],
        )

    def _get_df(
        self: typing.Self,
        connector_data: ConnectorData,
        logger: logging.Logger,
        fetch_params_dict: typing.Optional[dict] = None,
    ) -> pd.DataFrame:
        """ Get vehicle status for Go Measure inputting

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

        # Close the status of vehicles that have left the fleet
        combined_df = fetch_vehicle_data(
            df=combined_df,
            cols_to_fetch={
                VehiclesModel.entry_into_fleet_date.name,
                VehiclesModel.exit_from_fleet_date.name,
            },
            connector_data=connector_data,
            logger=logger,
        )
        current_date = datetime.now(
            tz=combined_df[VehiclesModel.entry_into_fleet_date.name].dt.tz
        )
        combined_df[VehicleStatusModel.vehicle_status.name] = (
            combined_df[VehicleStatusModel.vehicle_status.name].mask(
                ~series_is_nan(combined_df[VehiclesModel.entry_into_fleet_date.name])
                & (combined_df[VehiclesModel.exit_from_fleet_date.name].fillna(current_date) < current_date),
                VehicleStatus.closed.value,
            )
        )

        # Regroup based on id
        combined_df = self.regroup_df(
            dup_df=combined_df,
            id_cols=[
                VehiclesModel.plate_number.name,
            ],
            logger=logger,
        ).reset_index(drop=True)

        combined_df = self.fill_missing_cols(df=combined_df)
        combined_df[VehicleStatusModel.vehicle_status_start_date.name] = (
            combined_df[VehicleStatusModel.vehicle_status_start_date.name].fillna(
                current_date
            )
        )

        return combined_df[self.return_column_names()]

    def to_sql(
        self: typing.Self,
        data_df: pd.DataFrame,
        organization_id: UUID,
        session: Session,
        logger: logging.Logger,
        update_values: str = 'keep',
        columns: typing.Optional[typing.List[str]] = None,
    ) -> None:
        """ Inserts the passed data_df to the input_table db table mapping

        :param data_df: a dataframe containing the data to be uploaded to SQL
        :param organization_id: a db valid organization uuid
        :param session: a SQLAlchemy session
        :param logger: logging.Logger
        :param update_values: 'overwrite', 'keep', or null_only to determine
            how to handle existing rows in the db
        """
        super().to_sql(
            data_df=data_df,
            organization_id=organization_id,
            session=session,
            logger=logger,
            update_values=update_values,
            columns=columns,
        )


if __name__ == "__main__":
    logger = gen_logger('vehicle_table')
    organization_name = 'groupe-batisseur-d-avenir'
    root_folder = os.environ['_soongo_data_folder']
    organization_folder = os.path.join(
        root_folder,
        organization_name,
    )
    connector_data = ConnectorData(
        root_folder=root_folder,
        organization_name=organization_name,
    )
    vehicle_status_table = VehiclesStatusInputTable()
    status_df = vehicle_status_table.get(
        connector_data=connector_data,
        logger=logger,
    )

    vehicle_status_table.check_columns(
        data_df=status_df,
        logger=logger,
    )

    status_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{vehicle_status_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
