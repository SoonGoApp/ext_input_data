""" Script to calculate the expense claims table to load in database."""
import logging
import os
import typing

import pandas as pd

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (ClaimsModel, CollaboratorsModel,
                                     SoonGoRecordsModel)
from soongo_data.input_tables.employees_table import EmployeesInputTable
from soongo_data.input_tables.expense_utils import infer_amounts_and_tax
from soongo_data.sql_mappings import ExpenseClaimsTable
from soongo_data.utils.enums import ExpenseType
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id,
                                            match_soongo_employee_id)
from soongo_data.utils.logging_utils import gen_logger


@add_input_table
class ExpenseClaimsInputTable(InputTable):

    def __init__(self):
        super().__init__(
            sql_mapping=ExpenseClaimsTable,
            date_col_name='expense_date',
            columns=[
                InputColumn.from_data_column(
                    column=CollaboratorsModel.soongo_collab_reference,
                    foreign_relationship=(
                        EmployeesInputTable().name,
                        CollaboratorsModel.soongo_collab_reference.name,
                    ),
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=ClaimsModel.expense_date,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=ClaimsModel.amount_tax_exc,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=ClaimsModel.deductible_vat,
                ),
                InputColumn.from_data_column(
                    column=ClaimsModel.net_amount,
                ),
                InputColumn.from_data_column(
                    column=ClaimsModel.currency,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=ClaimsModel.expense_type,
                    enum=ExpenseType,
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
                    column=ClaimsModel.quantity,
                ),
            ]
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
        expense_data = self.fetch_table_data(
            connector_data=connector_data,
            logger=logger,
            fetch_params_dict=fetch_params_dict,
        )
        expense_data = add_synchronization_id(expense_data, connector_data)
        if expense_data.empty:
            return expense_data

        # Compute amount ht, deductible_vat, and net
        expense_data = infer_amounts_and_tax(
            df=expense_data,
            logger=logger,
            connector_data=connector_data,
            category_col=ClaimsModel.expense_type.name,
        )
        if ClaimsModel.currency.name not in expense_data:
            expense_data[ClaimsModel.currency.name] = 'EUR'

        # Add soongo_employee_id and business unit
        expense_data = match_soongo_employee_id(
            table_to_match=expense_data,
            organization_name=connector_data.organization_name,
        )

        # Fill missing cols
        expense_data = self.fill_missing_cols(
            df=expense_data,
        )

        return expense_data[self.return_column_names()]


if __name__ == "__main__":
    logger = gen_logger('expense_claims_table')
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

    claims_input_table = ExpenseClaimsInputTable()
    claims_df = claims_input_table.get(
        connector_data=connector_data,
        logger=logger,
    )

    employee_table = EmployeesInputTable().get(
        connector_data=connector_data,
        logger=logger,
    )
    claims_input_table.check_columns(
        data_df=claims_df,
        collaborators=employee_table,
        logger=logger,
    )
    claims_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{claims_input_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
