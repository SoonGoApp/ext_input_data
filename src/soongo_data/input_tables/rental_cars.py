""" Script to calculate the incident table to load in database."""
import logging
import os
import typing

import pandas as pd

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (CollaboratorsModel, RentalCarsModel,
                                     SoonGoRecordsModel)
from soongo_data.input_tables.employees_table import EmployeesInputTable
from soongo_data.input_tables.expense_utils import infer_amounts_and_tax
from soongo_data.sql_mappings import RentalCarsTable
from soongo_data.utils.enums import TravelTypes
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id,
                                            match_soongo_employee_id)
from soongo_data.utils.logging_utils import gen_logger


@add_input_table
class RentalCarsInputTable(InputTable):
    def __init__(self: typing.Self):
        super().__init__(
            sql_mapping=RentalCarsTable,
            date_col_name='billing_date',
            columns=[
                InputColumn.from_data_column(
                    column=RentalCarsModel.expense_id,
                    unique=True,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=RentalCarsModel.booking_date,
                    format=r'\d{4}-\d{2}-\d{2}',
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=RentalCarsModel.billing_date,
                    format=r'\d{4}-\d{2}-\d{2}',
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.soongo_collab_reference,
                    foreign_relationship=(
                        EmployeesInputTable().name,
                        CollaboratorsModel.soongo_collab_reference.name,
                    ),
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=RentalCarsModel.supplier,
                ),
                InputColumn.from_data_column(
                    column=RentalCarsModel.car_segment,
                ),
                InputColumn.from_data_column(
                    column=RentalCarsModel.car_type,
                ),
                InputColumn.from_data_column(
                    column=RentalCarsModel.start_city,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=RentalCarsModel.start_country_name,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=RentalCarsModel.arrival_city,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=RentalCarsModel.arrival_country_name,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=RentalCarsModel.start_datetime,
                    nullable=False,
                    format=r'\d{4}-\d{2}-\d{2}',
                ),
                InputColumn.from_data_column(
                    column=RentalCarsModel.end_datetime,
                    nullable=False,
                    format=r'\d{4}-\d{2}-\d{2}',
                ),
                InputColumn.from_data_column(
                    column=RentalCarsModel.amount_tax_exc,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=RentalCarsModel.deductible_vat,
                ),
                InputColumn.from_data_column(
                    column=RentalCarsModel.net_amount,
                ),
                InputColumn.from_data_column(
                    column=RentalCarsModel.amount_fees,
                    sql_name='amount_fee',
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
        # Get rental data
        rental_car_df = self.fetch_table_data(
            connector_data=connector_data,
            logger=logger,
            fetch_params_dict=fetch_params_dict,
        )
        rental_car_df = add_synchronization_id(rental_car_df, connector_data)
        if rental_car_df.empty:
            return rental_car_df

        if RentalCarsModel.travel_type.name in rental_car_df.columns:
            rental_car_df = rental_car_df[
                (
                    rental_car_df[RentalCarsModel.travel_type.name] ==
                    TravelTypes.rental_car.value
                )
            ]
        else:
            rental_car_df[RentalCarsModel.travel_type.name] = (
                TravelTypes.rental_car.value
            )
        rental_car_df = infer_amounts_and_tax(
            df=rental_car_df,
            logger=logger,
            connector_data=connector_data,
            category_col=RentalCarsModel.travel_type.name,
        )

        # Add soongo_employee_id and business unit
        rental_car_df = match_soongo_employee_id(
            table_to_match=rental_car_df,
            organization_name=connector_data.organization_name,
        )
        rental_car_df = self.fill_missing_cols(
            df=rental_car_df,
        )

        return rental_car_df[self.return_column_names()]


if __name__ == "__main__":
    logger = gen_logger('rental_cars_table')
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
    rental_car_table = RentalCarsInputTable()
    rental_car_df = rental_car_table.get(
        connector_data=connector_data,
        logger=logger,
    )
    rental_car_table.check_columns(
        data_df=rental_car_df,
        collaborators=EmployeesInputTable().get(
            connector_data=connector_data,
            logger=logger,
        ),
        logger=logger,
    )
    rental_car_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{rental_car_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
