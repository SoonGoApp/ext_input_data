""" Script to calculate the vehicle_connector_ids table."""
import logging
import os
import typing

import pandas as pd
import sqlalchemy as sa

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import SoonGoRecordsModel, VehiclesModel
from soongo_data.input_tables.vehicles_table import VehiclesInputTable
from soongo_data.utils.input_tables import (
    InputColumn, InputTable,
    add_input_table,
    add_synchronization_id
)
from soongo_data.sql_mappings import (
    VehiclesTable, VehicleConnectorIdsTable, ConnectorsTable
)
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.type import series_is_nan


@add_input_table
class VehicleConnectorIdsInputTable(InputTable):

    def __init__(self: typing.Self):
        super().__init__(
            sql_mapping=VehicleConnectorIdsTable,
            columns=[
                InputColumn.from_data_column(
                    column=VehiclesModel.plate_number,
                    foreign_relationship=(
                        VehiclesInputTable().name,
                        VehiclesModel.plate_number.name,
                    ),
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.vehicle_connector_id,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=SoonGoRecordsModel.connector_name,
                    nullable=False,
                    is_id=True,
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
                    column=SoonGoRecordsModel.ext_api_params,
                    nullable=True,
                    is_id=True,
                    sql_name='add_params',
                ),
            ]
        )

    def _get_df(
        self: typing.Self,
        connector_data: ConnectorData,
        logger: logging.Logger,
        fetch_params_dict: typing.Optional[dict] = None,
    ) -> pd.DataFrame:
        """ Get collaborator connector ids table

        :param connector_data: connector Data Class with all folders
        """
        combined_df = self.fetch_table_data(
            connector_data=connector_data,
            logger=logger,
            fetch_params_dict=fetch_params_dict,
        )
        combined_df = add_synchronization_id(combined_df, connector_data)
        if combined_df.empty:
            return combined_df

        # No point in recording if no connector id
        combined_df = combined_df.loc[
            ~series_is_nan(
                combined_df[VehiclesModel.vehicle_connector_id.name]
            )
        ]

        # Regroup based on id
        combined_df = self.regroup_df(
            dup_df=combined_df,
            id_cols=[
                VehiclesModel.plate_number.name,
                SoonGoRecordsModel.connector_name.name,
                SoonGoRecordsModel.ext_api_params.name,
            ],
            logger=logger,
        ).reset_index(drop=True)

        return combined_df[self.return_column_names()]

    def to_sql(
        self: typing.Self,
        data_df: pd.DataFrame,
        organization_id: str,
        session: sa.orm.Session,
        logger: logging.Logger,
        update_values: str = 'null_only',
        columns: typing.List[str] = None,
    ) -> None:
        """ Write the data to the database

        :param data_df: DataFrame to write
        :param organization_id: Organization ID to write to
        :param session: SQLAlchemy session to use
        :param logger: Logger to use
        :param update_values: How to update values, default is 'null_only'
        :param columns: Columns to write, default is None (all columns)
        """

        masternaut_plates = data_df.loc[
            data_df[SoonGoRecordsModel.connector_name.name] == 'MASTERNAUT',
            VehiclesModel.plate_number.name
        ].unique()
        if (masternaut_plates.size > 0) and update_values in ('overwrite', 'inc_null'):
            logger.warning(
                f'Replacing masternaut ids: {masternaut_plates}'
            )
            masternaut_id = session.query(
                ConnectorsTable.id
            ).filter(ConnectorsTable.name == 'MASTERNAUT').scalar()

            vehicle_subquery = sa.select(
                VehiclesTable.id
            ).filter(
                VehiclesTable.plate_number.in_(masternaut_plates)
            )

            delete_query = sa.delete(
                VehicleConnectorIdsTable
            ).where(
                VehicleConnectorIdsTable.vehicle_id.in_(vehicle_subquery),
                VehicleConnectorIdsTable.connector_id == masternaut_id,
            )
            session.execute(delete_query)

        super().to_sql(
            data_df=data_df,
            organization_id=organization_id,
            session=session,
            logger=logger,
            update_values=update_values,
            columns=columns,
        )


if __name__ == "__main__":

    logger = gen_logger('vehicle_connector_ids')
    organization_name = 'acorus'
    root_folder = '/home/matthieuglotz/Documents/Data/soongo-local'
    organization_folder = os.path.join(
        root_folder,
        organization_name,
    )
    connector_data = ConnectorData(
        root_folder=root_folder,
        organization_name=organization_name,
    )
    vehicle_id_table = VehicleConnectorIdsInputTable()
    equipment_df = vehicle_id_table.get(
        connector_data=connector_data,
        logger=logger,
    )
    vehicle_id_table.check_columns(
        data_df=equipment_df,
        logger=logger,
        vehicles=VehiclesInputTable().get(
            connector_data=connector_data,
            logger=logger,
        ),
    )
    equipment_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{vehicle_id_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
