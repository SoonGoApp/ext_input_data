""" Script to calculate the incident table to load in database."""
import logging
import os
import typing

import pandas as pd

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (CollaboratorsModel, SoonGoRecordsModel,
                                     TrainPlaneTravelModel)
from soongo_data.input_tables.expense_utils import infer_amounts_and_tax
from soongo_data.sql_mappings import TrainsPlanesTable
from soongo_data.utils.enums import TicketTypes
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id,
                                            match_soongo_employee_id)
from soongo_data.utils.logging_utils import gen_logger


@add_input_table
class TravelInputTable(InputTable):

    def __init__(self: typing.Self):
        super().__init__(
            sql_mapping=TrainsPlanesTable,
            date_col_name='billing_date',
            columns=[
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.expense_id,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.leg_id,
                    is_id=True,
                    nullable=True,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.travel_type,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.booking_date,
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.billing_date,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.soongo_collab_reference,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.amount_tax_exc,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.deductible_vat,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.net_amount,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.airport_tax,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.ticket_type,
                    default=TicketTypes.unknown.value,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.leg_number,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.start_location_code,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.start_city,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.start_country_name,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.arrival_location_code,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.arrival_city,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.arrival_country_name,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.routing,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.transporter_name,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.supplier_alliance,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.cabin_class,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.start_datetime,
                    format=r'\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?',
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.end_datetime,
                    format=r'\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?',
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.layover_time,
                    format=r'(?:\d+j )?\d{2}:\d{2}'
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.distance,
                ),
                InputColumn.from_data_column(
                    column=TrainPlaneTravelModel.co2_footprint,
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
        """ Get vehicle table for Go Measure inputting

        :param gac_data: GacData with all data imported from gac

        :return: pandas dataframe with all columns from the vehicle table
        """
        # Get train plane data
        train_planes_df = self.fetch_table_data(
            connector_data=connector_data,
            logger=logger,
            fetch_params_dict=fetch_params_dict,
        )
        train_planes_df = add_synchronization_id(
            train_planes_df,
            connector_data,
        )
        if train_planes_df.empty:
            return train_planes_df

        train_planes_df = infer_amounts_and_tax(
            df=train_planes_df,
            logger=logger,
            connector_data=connector_data,
            category_col=TrainPlaneTravelModel.travel_type.name,
        )

        # Add soongo_employee_id and business unit
        train_planes_df = match_soongo_employee_id(
            table_to_match=train_planes_df,
            organization_name=connector_data.organization_name,
        )
        train_planes_df = self.fill_missing_cols(
            df=train_planes_df,
        )
        return train_planes_df[self.return_column_names()]


if __name__ == "__main__":
    logger = gen_logger('train_plane_table')
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

    travel_table = TravelInputTable()
    travel_df = travel_table.get(
        connector_data=connector_data,
        logger=logger,
    )
    travel_table.check_columns(
        data_df=travel_df,
        logger=logger,
    )
    travel_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{travel_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
