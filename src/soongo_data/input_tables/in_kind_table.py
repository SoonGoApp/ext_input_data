""" Script to calculate the in kind benefits table on which to compute impacts."""
import logging
import os
import typing
from uuid import UUID

import pandas as pd
import sqlalchemy as sa

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (
    TaxesModel,
    CollaboratorsModel,
    SoonGoRecordsModel
)
from soongo_data.sql_mappings import (InKindBenefitsTable)
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id,
                                            match_soongo_employee_id)
from soongo_data.utils.logging_utils import gen_logger


@add_input_table
class InKindBenefitsInputTable(InputTable):

    def __init__(self: typing.Self):
        super().__init__(
            sql_mapping=InKindBenefitsTable,
            columns=[
                InputColumn.from_data_column(
                    column=TaxesModel.ikb_start_date,
                    nullable=False,
                    is_id=True,
                    sql_name='date_from',
                ),
                InputColumn.from_data_column(
                    column=TaxesModel.ikb_end_date,
                    is_id=True,
                    sql_name='date_to',
                ),
                InputColumn.from_data_column(
                    column=TaxesModel.ikb_monthly_value,
                    nullable=False,
                    sql_name='monthly_amount',
                ),
                InputColumn.from_data_column(
                    column=TaxesModel.ikb_type,
                    nullable=False,
                    sql_name='type',
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.soongo_collab_reference,
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

        combined_df = match_soongo_employee_id(
            table_to_match=combined_df,
            organization_name=connector_data.organization_name
        )
        combined_df = self.fill_missing_cols(combined_df)

        return combined_df[self.return_column_names()]

    def to_sql(
        self: typing.Self,
        data_df: pd.DataFrame,
        organization_id: UUID,
        session: sa.orm.Session,
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
                """
                    select graphile_worker.add_job(
                        'refresh_materialized_view',
                        json_build_object(
                            'view',
                            'publ.in_kind_benefits_primitive_view'
                        )
                    )
                ;"""
            ),
        )


if __name__ == "__main__":
    logger = gen_logger('ikb_table')
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
    ikb_table = InKindBenefitsInputTable()
    ikb_df = ikb_table.get(
        connector_data=connector_data,
        logger=logger,

    )
    ikb_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{ikb_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
