""" Script to calculate the hotels table to load in database."""
import logging
import os
import typing

import pandas as pd

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (CollaboratorsModel, HotelsModel,
                                     SoonGoRecordsModel)
from soongo_data.input_tables.employees_table import EmployeesInputTable
from soongo_data.input_tables.expense_utils import infer_amounts_and_tax
from soongo_data.sql_mappings import HotelsTable
from soongo_data.utils.enums import TravelTypes
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id,
                                            match_soongo_employee_id)
from soongo_data.utils.logging_utils import gen_logger


@add_input_table
class HotelsInputTable(InputTable):
    def __init__(self):
        super().__init__(
            sql_mapping=HotelsTable,
            date_col_name='billing_date',
            columns=[
                InputColumn.from_data_column(
                    column=HotelsModel.expense_id,
                    unique=True,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.booking_date,
                    format=r'\d{4}-\d{2}-\d{2}',
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.billing_date,
                    format=r'\d{4}-\d{2}-\d{2}',
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel().soongo_collab_reference,
                    foreign_relationship=(
                        EmployeesInputTable().name,
                        CollaboratorsModel.soongo_collab_reference.name,
                    ),
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.supplier,
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.room_type,
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.start_city,
                    nullable=False,
                    sql_name='city_name',
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.start_country_name,
                    nullable=False,
                    sql_name='country_name',
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.room_count,
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.night_count,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.room_night_count,
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.price_per_room_night,
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.amount_tax_exc,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.deductible_vat,
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.net_amount,
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.amount_fees,
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.was_negotiated,
                ),
                InputColumn.from_data_column(
                    column=HotelsModel.approver,
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
        # Get hotel data
        hotel_df = self.fetch_table_data(
            connector_data=connector_data,
            logger=logger,
            fetch_params_dict=fetch_params_dict,
        )
        hotel_df = add_synchronization_id(hotel_df, connector_data)
        if hotel_df.empty:
            return hotel_df

        if HotelsModel.travel_type.name in hotel_df.columns:
            hotel_df = hotel_df.loc[
                (
                    hotel_df[HotelsModel.travel_type.name] ==
                    TravelTypes.hotels.value
                ),
            ]
        else:
            hotel_df[HotelsModel.travel_type.name] = (
                TravelTypes.hotels.value
            )

        hotel_df = infer_amounts_and_tax(
            df=hotel_df,
            logger=logger,
            connector_data=connector_data,
            category_col=HotelsModel.travel_type.name,
        )

        # Add soongo_employee_id and business unit
        hotel_df = match_soongo_employee_id(
            table_to_match=hotel_df,
            organization_name=connector_data.organization_name,
        )
        hotel_df = self.fill_missing_cols(
            df=hotel_df,
        )

        return hotel_df[self.return_column_names()]


if __name__ == "__main__":
    logger = gen_logger('hotels_table')
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
    hotel_table = HotelsInputTable()
    hotel_df = hotel_table.get(
        connector_data=connector_data,
        logger=logger,

    )
    hotel_table.check_columns(
        data_df=hotel_df,
        collaborators=EmployeesInputTable().get(
            connector_data=connector_data,
            logger=logger,
        ),
        logger=logger,
    )
    hotel_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{hotel_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
