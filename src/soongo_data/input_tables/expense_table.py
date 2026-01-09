""" Script to calculate the baseline kpis on which to compute impacts."""
import logging
import os
import typing
from uuid import UUID

import pandas as pd
import pytz
import sqlalchemy as sa
from sqlalchemy.orm import Session

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (AccidentsModel, BusinessUnitsModel,
                                     CollaboratorsModel,
                                     EquipmentsModel, ExpensesModel,
                                     SoonGoRecordsModel, VehiclesModel,
                                     VehicleContractsModel)
from soongo_data.input_tables.employees_table import EmployeesInputTable
from soongo_data.input_tables.expense_utils import infer_amounts_and_tax
from soongo_data.input_tables.vehicles_table import VehiclesInputTable
from soongo_data.sql_mappings import ExpensesTable
from soongo_data.utils.bu import get_cost_center, get_business_units
from soongo_data.utils.fetch import fetch_contract_data
from soongo_data.utils.enums import CostCategory, RentCategory
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id,
                                            check_no_future_dates,
                                            match_soongo_employee_id)
from soongo_data.utils.logging_utils import gen_logger


@add_input_table
class ExpensesInputTable(InputTable):

    def __init__(self):
        super().__init__(
            sql_mapping=ExpensesTable,
            date_col_name='billing_date',
            columns=[
                InputColumn.from_data_column(
                    column=ExpensesModel.expense_reference,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=ExpensesModel.supplier,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=ExpensesModel.billing_date,
                    nullable=False,
                    format=r'\d{4}-\d{2}-\d{2}',
                ),
                InputColumn.from_data_column(
                    column=ExpensesModel.amount_tax_exc,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=ExpensesModel.net_amount,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.plate_number,
                    foreign_relationship=(
                        VehiclesInputTable().name,
                        VehiclesModel.plate_number.name,
                    ),
                ),
                InputColumn.from_data_column(
                    column=ExpensesModel.vat_value,
                ),
                InputColumn.from_data_column(
                    column=ExpensesModel.deductible_vat,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.soongo_collab_reference,
                    foreign_relationship=(
                        EmployeesInputTable().name,
                        CollaboratorsModel.soongo_collab_reference.name,
                    ),
                ),
                InputColumn.from_data_column(
                    column=BusinessUnitsModel.business_unit,
                ),
                InputColumn.from_data_column(
                    column=ExpensesModel.soongo_category,
                    nullable=False,
                    enum=CostCategory,
                ),
                InputColumn.from_data_column(
                    column=ExpensesModel.quantity,
                    nullable=True,
                ),
                InputColumn.from_data_column(
                    column=EquipmentsModel.equipment_reference,
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
                    column=ExpensesModel.billing_reference,
                ),
                InputColumn.from_data_column(
                    column=ExpensesModel.transaction_start_date,
                ),
                InputColumn.from_data_column(
                    column=ExpensesModel.transaction_end_date,
                ),
                InputColumn.from_data_column(
                    column=ExpensesModel.expense_location,
                ),
                InputColumn.from_data_column(
                    column=ExpensesModel.product,
                ),
                InputColumn.from_data_column(
                    column=ExpensesModel.merchant_name,
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.accident_ref,
                ),
                InputColumn.from_data_column(
                    column=BusinessUnitsModel.billed_entity,
                )
            ],
        )

    def _get_df(
        self: typing.Self,
        connector_data: ConnectorData,
        logger: logging.Logger,
        fetch_params_dict: typing.Optional[dict] = None,
    ) -> pd.DataFrame:
        """ Get baseline fleet kpis for impact calculation

        :param gac_data: GacData with all data imported from gac
        :param havas_data: HavasData with all data imported from Havas
        :param logger: logger

        :return: pandas dataframe with kpis at vehicule level
        """
        expenses_df = self.fetch_table_data(
            connector_data=connector_data,
            logger=logger,
            fetch_params_dict=fetch_params_dict,
        )

        expenses_df = get_business_units(
            expenses_df,
            logger=logger,
            organization_name=connector_data.organization_name,
            source_connectors_override=['*'],  # build BU whenever possible
        )

        # check dates
        check_no_future_dates(
            date_tol=pd.Timestamp.now() + pd.DateOffset(months=3),
            data_df=expenses_df,
            date_var=ExpensesModel.billing_date.name,
            raise_error=True,
            table_name=self.name,
            logger=logger,
        )
        check_no_future_dates(
            date_tol=pd.Timestamp.now(),
            data_df=expenses_df,
            date_var=ExpensesModel.billing_date.name,
            raise_error=False,
            table_name=self.name,
            logger=logger,
        )

        expenses_df = add_synchronization_id(expenses_df, connector_data)
        if expenses_df.empty:
            return expenses_df

        expenses_df = infer_amounts_and_tax(
            df=expenses_df,
            logger=logger,
            connector_data=connector_data,
            category_col=ExpensesModel.soongo_category.name,
        )
        expenses_df = self.detect_exceptional_rents(
            data_df=expenses_df,
            organization_slug=connector_data.organization_name,
            logger=logger,
        )

        expenses_df = match_soongo_employee_id(
            table_to_match=expenses_df,
            organization_name=connector_data.organization_name,
        )
        expenses_df = self.fill_missing_cols(df=expenses_df)

        return expenses_df[self.return_column_names()]

    def to_sql(
        self: typing.Self,
        data_df: pd.DataFrame,
        organization_id: UUID,
        session: Session,
        logger: logging.Logger,
        update_values: str = 'null_only',
        columns: typing.Optional[typing.List[str]] = None,
    ) -> pd.DataFrame:
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

        session.execute(
            sa.text(
                "select graphile_worker.add_job('refresh_materialized_view', json_build_object('view', 'publ.expense_primitive_view'));"),
        )
        session.execute(
            sa.text(
                'delete from publ.primitive_cached_values where organization_id = :org_id;'
            ),
            params={
                'org_id': organization_id,
            },
        )

    def detect_exceptional_rents(
        self: typing.Self,
        data_df: pd.DataFrame,
        organization_slug: str,
        logger: logging.Logger,
        threshold_exception: float = 2,
    ) -> pd.DataFrame:
        """ Detect exceptional rents based on amount_tax_exc > 1000 and
            recategorize

        :param data_df: DataFrame with expense data
        :param logger: logger

        :returns: pd Series of boolean values indicating if rent is exceptional
        """
        if ExpensesModel.soongo_category.name not in data_df.columns:
            raise ValueError('soongo_category column required to detect rents')
        if ExpensesModel.amount_tax_exc.name not in data_df.columns:
            raise ValueError('amount_tax_exc column required to detect exceptional rents')
        if VehiclesModel.plate_number.name not in data_df.columns:
            logger.warning(
                'plate_number column not in expense table, cannot fetch contract rent'
            )
            return data_df

        is_rent = data_df[ExpensesModel.soongo_category.name].isin(
            [cat.value for cat in RentCategory]
        )
        data_df = fetch_contract_data(
            df=data_df,
            cols_to_fetch=[VehicleContractsModel.total_rent_tax_exc.name],
            logger=logger,
            organization_slug=organization_slug,
        )
        is_exceptional_rent = is_rent & (
            data_df[VehicleContractsModel.total_rent_tax_exc.name].fillna(0) > 0
        ) & (
            data_df[ExpensesModel.amount_tax_exc.name] > (
                threshold_exception * data_df[VehicleContractsModel.total_rent_tax_exc.name]
            )
        )

        n_exceptional_rents = is_exceptional_rent.sum()
        if n_exceptional_rents > 0:
            logger.warning(
                f'Detected {n_exceptional_rents} exceptional rents '
                f'with amount_tax_exc > {threshold_exception} the rent. '
                f'Recategorizing as {CostCategory.financial_rent_adjustment.name}.'
            )

        data_df[ExpensesModel.soongo_category.name] = data_df[
            ExpensesModel.soongo_category.name
        ].mask(
            is_exceptional_rent,
            CostCategory.financial_rent_adjustment.value,
        )

        return data_df


if __name__ == "__main__":

    logger = gen_logger('expense_table')
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

    expense_table = ExpensesInputTable()
    expense_df = expense_table.get(
        connector_data=connector_data,
        logger=logger,
    )
    """
    expense_table.check_columns(
        data_df=expense_df,
        collaborators=EmployeesInputTable().get(
            connector_data=connector_data,
            logger=logger,
        ),
        vehicles=VehiclesInputTable().get(
            connector_data=connector_data,
            logger=logger,
        ),
        logger=logger,
    )
    """
    expense_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{expense_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
