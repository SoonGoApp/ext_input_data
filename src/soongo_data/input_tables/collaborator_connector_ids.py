""" Script to calculate the collaborator_connector_ids table."""
import logging
import os
import typing

import pandas as pd

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import CollaboratorsModel, SoonGoRecordsModel
from soongo_data.input_tables.employees_table import EmployeesInputTable
from soongo_data.sql_mappings import CollaboratorConnectorIdsTable
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id,
                                            match_soongo_employee_id)
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.type import series_is_nan


@add_input_table
class CollaboratorConnectorIdsInputTable(InputTable):

    def __init__(self: typing.Self):
        super().__init__(
            sql_mapping=CollaboratorConnectorIdsTable,
            columns=[
                InputColumn.from_data_column(
                    column=CollaboratorsModel.soongo_collab_reference,
                    foreign_relationship=(
                        EmployeesInputTable().name,
                        CollaboratorsModel.soongo_collab_reference.name,
                    ),
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.collaborator_connector_id,
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
                combined_df[CollaboratorsModel.collaborator_connector_id.name]
            )
        ]

        combined_df = match_soongo_employee_id(
            table_to_match=combined_df,
            organization_name=connector_data.organization_name,
        )
        # Regroup based on id
        combined_df = self.regroup_df(
            dup_df=combined_df,
            id_cols=[
                CollaboratorsModel.soongo_collab_reference.name,
                SoonGoRecordsModel.connector_name.name,
                SoonGoRecordsModel.ext_api_params.name,
            ],
            logger=logger,
        ).reset_index(drop=True)

        return combined_df.loc[
            ~series_is_nan(
                combined_df[CollaboratorsModel.soongo_collab_reference.name]
            ),
            self.return_column_names(),
        ]


if __name__ == "__main__":

    logger = gen_logger('collaborator_connector_ids')
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
    equipment_table = CollaboratorConnectorIdsInputTable()
    equipment_df = equipment_table.get(
        connector_data=connector_data,
        logger=logger,
    )
    equipment_table.check_columns(
        data_df=equipment_df,
        logger=logger,
        collaborators=EmployeesInputTable().get(
            connector_data=connector_data,
            logger=logger,
        ),
    )
    equipment_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{equipment_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
