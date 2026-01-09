""" Script to calculate the business_unit_connector_ids table."""
import logging
import os
import typing

import pandas as pd

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import BusinessUnitsModel, SoonGoRecordsModel
from soongo_data.sql_mappings import BusinessUnitConnectorIdsTable
from soongo_data.utils.bu import get_business_units
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id)
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.type import series_is_nan


@add_input_table
class BusinessUnitConnectorIdsInputTable(InputTable):

    def __init__(self: typing.Self):
        super().__init__(
            sql_mapping=BusinessUnitConnectorIdsTable,
            columns=[
                InputColumn.from_data_column(
                    column=BusinessUnitsModel.business_unit,
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=BusinessUnitsModel.business_unit_connector_id,
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

        # get business_unit
        combined_df = get_business_units(
            entity_df=combined_df,
            logger=logger,
            organization_name=connector_data.organization_name,
        )

        # No point in recording if no connector id
        combined_df = combined_df.loc[
            ~series_is_nan(
                combined_df[BusinessUnitsModel.business_unit_connector_id.name]
            )
        ]

        # No point in recording if no business unit
        combined_df = combined_df.loc[
            ~series_is_nan(
                combined_df[BusinessUnitsModel.business_unit.name]
            )
        ]

        # Regroup based on id
        combined_df = self.regroup_df(
            dup_df=combined_df,
            id_cols=[
                BusinessUnitsModel.business_unit.name,
                SoonGoRecordsModel.connector_name.name,
                SoonGoRecordsModel.ext_api_params.name,
            ],
            logger=logger,
        ).reset_index(drop=True)

        return combined_df.loc[
            ~series_is_nan(
                combined_df[BusinessUnitsModel.business_unit_connector_id.name]
            ),
            self.return_column_names(),
        ]


if __name__ == "__main__":

    logger = gen_logger('business_unit_connector_ids')
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
    bu_con_id_table = BusinessUnitConnectorIdsInputTable()
    bu_con_id_df = bu_con_id_table.get(
        connector_data=connector_data,
        logger=logger,
    )
    bu_con_id_table.check_columns(
        data_df=bu_con_id_df,
        logger=logger,
    )
    bu_con_id_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{bu_con_id_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
