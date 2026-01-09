""" Script to calculate the vehicle association table."""
import logging
import os
import typing
from datetime import date

import numpy as np
import pandas as pd
import sqlalchemy as sa

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (CollaboratorsModel, ExpensesModel,
                                     SoonGoRecordsModel,
                                     VehicleAssociationsModel,
                                     VehicleContractsModel, VehiclesModel)
from soongo_data.input_tables.employees_table import EmployeesInputTable
from soongo_data.input_tables.vehicles_table import VehiclesInputTable
from soongo_data.sql_mappings import VehicleAttributionsTable
from soongo_data.utils.enums import CostCategory
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            NoMatchedTable, add_input_table,
                                            add_synchronization_id,
                                            combine_connector_data,
                                            fetch_organization_params,
                                            match_soongo_employee_id)
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.type import series_is_nan

pd.set_option('future.no_silent_downcasting', True)

# Define abbreviations (purely stylistic)
PLATE_COL = VehiclesModel.plate_number.name
EMPLOYEE_COL = CollaboratorsModel.soongo_collab_reference.name
ASSOCIATION_START = VehicleAssociationsModel.association_start_date.name
ASSOCIATION_END = VehicleAssociationsModel.association_end_date.name
ASSOCIATION_COLS = [
    PLATE_COL,
    EMPLOYEE_COL,
]


@add_input_table
class VehicleAssociationsInputTable(InputTable):

    def __init__(self):
        super().__init__(
            sql_mapping=VehicleAttributionsTable,
            columns=[
                InputColumn.from_data_column(
                    column=VehiclesModel.plate_number,
                    nullable=False,
                    foreign_relationship=(
                        VehiclesInputTable().name,
                        PLATE_COL,
                    ),
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.soongo_collab_reference,
                    foreign_relationship=(
                        EmployeesInputTable().name,
                        EMPLOYEE_COL,
                    ),
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=VehicleAssociationsModel.assigned_service,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=VehicleAssociationsModel.association_start_date,
                    is_id=True,
                    sql_name='date_from',
                ),
                InputColumn.from_data_column(
                    column=VehicleAssociationsModel.association_end_date,
                    sql_name='date_to',
                ),
                InputColumn.from_data_column(
                    column=VehicleAssociationsModel.daily_participation,
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
        """ Get vehicle assignment table.

        Works by first fetch all data on financial rent, checking if a collaborator
        was associated with a plate on that rent, deducting from this data the
        start date and end date for which the car was assigned to the collaborator.
        It then combines that data with other association start and end date source
        from the connectors. Information which specifies the name of the driver
        takes priority over information for which it is unknown or unassigned.

        :param connector_data: full connector data

        :return: pandas dataframe with all columns from the vehicle table
        """
        # Fetch data
        association_df = self.fetch_table_data(
            connector_data=connector_data,
            logger=logger,
            fetch_params_dict=fetch_params_dict,
        )
        if association_df.empty:
            return association_df
        association_df = association_df[~series_is_nan(association_df[PLATE_COL])]

        # Add soongo employee id and daily participation data
        association_df = match_soongo_employee_id(
            table_to_match=association_df,
            organization_name=connector_data.organization_name,
        )
        col_to_drop = {
            CollaboratorsModel.employee_full_name.name,
            CollaboratorsModel.organization_collaborator_id.name,
        }.intersection(
            association_df.columns
        )
        if col_to_drop:
            association_df.drop(
                columns=list(col_to_drop),
                inplace=True,
            )

        # Check data
        association_df = add_synchronization_id(association_df, connector_data)
        association_df = self.fill_missing_cols(
            df=association_df,
        )
        unique_associations = association_df[
            self.return_column_names()
        ].drop_duplicates(
            ASSOCIATION_COLS + [
                ASSOCIATION_START,
                ASSOCIATION_END,
                VehicleAssociationsModel.assigned_service.name,
                VehicleAssociationsModel.daily_participation.name,
                ]
        )
        unique_associations[VehicleAssociationsModel.daily_participation.name] = (
            unique_associations[VehicleAssociationsModel.daily_participation.name].fillna(0)
        )

        self.check_dates(unique_associations)

        inconsistent_dates = (
            unique_associations[ASSOCIATION_START] >
            unique_associations[ASSOCIATION_END]
        )

        if inconsistent_dates.any():
            inconsistent_ids = unique_associations[
                inconsistent_dates,
                PLATE_COL,
            ].drop_duplicates()
            raise ValueError(
                'Incoherent association values for the following association ids'
                f' {inconsistent_ids}'
            )

        return unique_associations.loc[
            ~series_is_nan(unique_associations[ASSOCIATION_START])  # mandatory
            & (
                ~series_is_nan(unique_associations[CollaboratorsModel.soongo_collab_reference.name])
                |
                ~series_is_nan(unique_associations[VehicleAssociationsModel.assigned_service.name])
            ),
            self.return_column_names()
        ]

    @staticmethod
    def check_dates(association_df: pd.DataFrame) -> None:
        """ Ensure that start and end dates are consistent within a DataFrame

        :param association_df: DataFrame with association data

        :raises ValueError: if there are inconsistent start / end dates
        """
        unique_associations = association_df.loc[
            pd.notna(association_df[ASSOCIATION_START]),
            [
                PLATE_COL,
                EMPLOYEE_COL,
                ASSOCIATION_START,
                ASSOCIATION_END,
            ],
        ].drop_duplicates()

        # Validate with Quartus for EMPLOYEES with multiple cars
        unique_associations = unique_associations.sort_values(
            by=[PLATE_COL, ASSOCIATION_START, ASSOCIATION_END],
            ascending=True,
        )

        # Check if start_date when previous end_date priority is greater
        unique_associations['previous_end_date'] = unique_associations.groupby(
            PLATE_COL
        ).shift()[ASSOCIATION_END].fillna(
            unique_associations[ASSOCIATION_START]
        )  # When no previous, consider True
        dates_aligned = (
            unique_associations[ASSOCIATION_START] >=
            unique_associations['previous_end_date']
        ) | series_is_nan(unique_associations[ASSOCIATION_START])

        # Raise error if erroneous records
        incorrect_values = unique_associations.loc[
            ~dates_aligned,
            PLATE_COL
        ].unique()
        if len(incorrect_values):
            raise ValueError(
                f'There are {len(incorrect_values)} start_date / previous '
                f'end date incoherence in the data for col '
                f'{PLATE_COL}: {incorrect_values}'
            )

        # Check if end_date when next start priority is greater
        unique_associations['next_start_date'] = unique_associations.groupby(
            PLATE_COL
        ).shift(-1)[ASSOCIATION_START].fillna(
            unique_associations[ASSOCIATION_END]
        )  # When no previous, consider True

        # If no association_start available no correct order available.
        dates_aligned = (
            unique_associations[ASSOCIATION_END] <=
            unique_associations['next_start_date']
        ) | series_is_nan(unique_associations[ASSOCIATION_END])

        # Raise if erroneous records
        incorrect_values = unique_associations.loc[
            ~dates_aligned,
            PLATE_COL
        ].unique()
        if len(incorrect_values):
            raise ValueError(
                f'There are {len(incorrect_values)} end_date / next start'
                f' date incoherence in the data given plate_number:'
                f' {incorrect_values}'
            )


if __name__ == "__main__":
    logger = gen_logger('associations_table')
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
    association_table = VehicleAssociationsInputTable()
    association_df = association_table.get(
        connector_data=connector_data,
        logger=logger,
    )
    association_table.check_columns(
        data_df=association_df,
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
    association_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{association_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
