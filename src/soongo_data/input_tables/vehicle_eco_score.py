""" scritp to fetch vehicle eco score data from Masternaut API and load it"""
import logging
import os
import typing

import pandas as pd

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (
    SoonGoRecordsModel,
    VehicleEcoScoreModel,
    VehiclesModel
)
from soongo_data.sql_mappings import (VehicleEcoScoreTable)
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id)
from soongo_data.utils.logging_utils import gen_logger

@add_input_table
class VehicleEcoScoreInputTable(InputTable):
    def __init__(self: typing.Self):
        super().__init__(
            sql_mapping=VehicleEcoScoreTable,
            columns=[
                InputColumn.from_data_column(
                    column=VehiclesModel.plate_number,
                    nullable=False,
                    is_id=True,
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
                    column=VehicleEcoScoreModel.date_from,
                    sql_name='date_from',
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=VehicleEcoScoreModel.date_to,
                    sql_name='date_to',
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=VehicleEcoScoreModel.score_type,
                    nullable=False,
                    sql_name='score_type',
                ),
                InputColumn.from_data_column(
                    column=VehicleEcoScoreModel.score,
                    nullable=False,
                    sql_name='score',
                ),
            ]
        )

    def _get_df(
        self: typing.Self,
        connector_data: ConnectorData,
        logger: logging.Logger,
        fetch_params_dict: typing.Optional[dict] = None,
    ) -> pd.DataFrame:
        """ Get Employees tables

        :param connector_data: Connector Data Class with all folders
        :param havas_data: Havas Data Class with all folders
        """
        combined_df = self.fetch_table_data(
            connector_data=connector_data,
            logger=logger,
            fetch_params_dict=fetch_params_dict,
        )
        
        combined_df = add_synchronization_id(combined_df, connector_data)
        if combined_df.empty:
            return combined_df

        combined_df = self.fill_missing_cols(combined_df)

        return combined_df[self.return_column_names()]


if __name__ == "__main__":
    logger = gen_logger('vehicle_eco_score')
    organization_name = 'acorus'
    root_folder = os.environ['_soongo_data_folder']
    organization_folder = os.path.join(
        root_folder,
        organization_name,
    )
    connector_data = ConnectorData(
        root_folder=root_folder,
        organization_name=organization_name,
    )
    vehicle_eco_score_input_table = VehicleEcoScoreInputTable()

    ves_df = vehicle_eco_score_input_table.get(
        connector_data=connector_data,
        logger=logger,

    )
    ves_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{vehicle_eco_score_input_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
