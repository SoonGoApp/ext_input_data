""" Script to calculate the incident table to load in database."""
import logging
import os
import typing

import pandas as pd
import sqlalchemy as sa

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (AccidentsModel, CollaboratorsModel,
                                     SoonGoRecordsModel, VehiclesModel)
from soongo_data.input_tables.employees_table import EmployeesInputTable
from soongo_data.input_tables.vehicles_table import VehiclesInputTable
from soongo_data.sql_mappings import AccidentsTable
from soongo_data.utils.enums import (AccidentContextTypes,
                                     AccidentGarageStatus,
                                     AccidentInsurerStatus, AccidentTypes,
                                     ResponsibilityTypes)
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id,
                                            get_collab_from_plate,
                                            match_soongo_employee_id)
from soongo_data.utils.logging_utils import gen_logger


@add_input_table
class AccidentsInputTable(InputTable):

    def __init__(self: typing.Self):
        super().__init__(
            sql_mapping=AccidentsTable,
            date_col_name='accident_date',
            columns=[
                InputColumn.from_data_column(
                    column=AccidentsModel.accident_date,
                    format=r'\d{4}-\d{2}-\d{2}',
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.accident_ref,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.plate_number,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.accident_type,
                    enum=AccidentTypes,
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.accident_context,
                    enum=AccidentContextTypes,
                    sql_name='context',
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.responsibility,
                    enum=ResponsibilityTypes,
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.third_party,
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.insurer,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.soongo_collab_reference,
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.insurer_cost,
                    sql_name='cost_insurer',
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.self_insurance_cost,
                    sql_name='cost_self_insurance',
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.insurance_deductible_cost,
                    sql_name='cost_deductible',
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.commute_accident,
                    sql_name='was_commute',
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.weekend_accident,
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.accident_location,
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
                    column=AccidentsModel.insurer_status,
                    enum=AccidentInsurerStatus,
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.garage_status,
                    enum=AccidentGarageStatus,
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.opening_date,
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.closing_date,
                ),
                InputColumn.from_data_column(
                    column=AccidentsModel.insurer_context,
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
        accident_df = self.fetch_table_data(
            connector_data=connector_data,
            logger=logger,
            fetch_params_dict=fetch_params_dict,
        )
        accident_df = add_synchronization_id(accident_df, connector_data)
        if accident_df.empty:
            return accident_df

        # Add soongo_employee_id and business unit
        accident_df = match_soongo_employee_id(
            table_to_match=accident_df,
            organization_name=connector_data.organization_name,
        )
        accident_df = get_collab_from_plate(
            table_to_match=accident_df,
            organization_name=connector_data.organization_name,
            date_col=AccidentsModel.accident_date.name,
            logger=logger,
        )
        if AccidentsModel.self_insurance_cost.name not in accident_df.columns:
            accident_df[AccidentsModel.self_insurance_cost.name] = 0.0
        if (
            AccidentsModel.insurance_deductible_cost.name
            not in accident_df.columns
        ) and (AccidentsModel.organization_cost.name in accident_df.columns):
            accident_df[AccidentsModel.insurance_deductible_cost.name] = (
                accident_df[AccidentsModel.organization_cost.name] -
                accident_df[AccidentsModel.self_insurance_cost.name]
            ).fillna(0)
        elif AccidentsModel.insurance_deductible_cost.name in accident_df.columns:
            accident_df[AccidentsModel.insurance_deductible_cost.name] = (
                accident_df[AccidentsModel.insurance_deductible_cost.name].fillna(
                    0
                )
            )

        if (
            (AccidentsModel.insurer_cost.name not in accident_df.columns)
            and
            (AccidentsModel.total_accident_cost.name in accident_df.columns)
            and
            (AccidentsModel.organization_cost.name in accident_df.columns)
        ):
            accident_df[AccidentsModel.insurer_cost.name] = (
                accident_df[AccidentsModel.total_accident_cost.name] -
                accident_df[AccidentsModel.organization_cost.name]
            )

        self.fill_missing_cols(df=accident_df)

        return accident_df[self.return_column_names()]

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
            (columns is None) or
            (AccidentsModel.insurer_status.name in columns)
        ):
            # Because many modifications happen in app we cannot modify status
            logger.warning(
                'Accident table insurer status cannot be overwritten '
                'modifying update_values argument to null_only'
            )
            update_values = 'null_only'

        super().to_sql(
            data_df,
            organization_id,
            session,
            logger,
            update_values,
            columns,
        )

        session.execute(
            sa.text('refresh materialized view publ.accidents_view;')
        )


if __name__ == "__main__":
    logger = gen_logger('accident_table')
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
    accident_table = AccidentsInputTable()
    accident_df = accident_table.get(
        connector_data=connector_data,
        logger=logger,
    )
    employee_table = EmployeesInputTable().get(
        connector_data=connector_data,
        logger=logger,
    )
    accident_table.check_columns(
        data_df=accident_df,
        collaborators=employee_table,
        vehicles=VehiclesInputTable().get(
            connector_data=connector_data,
            logger=logger,
        ),
        logger=logger,
    )
    accident_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{accident_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
