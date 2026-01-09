""" Script to calculate the vehicle_services table."""
import logging
import os
import typing

import pandas as pd
import sqlalchemy as sa

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (
    VehiclesModel, VehicleMaintenanceModel, SoonGoRecordsModel
)
from soongo_data.utils.input_tables import (
    InputColumn, InputTable,
    add_input_table,
    add_synchronization_id,
)
from soongo_data.sql_mappings import VehicleControls, VehiclesTable
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.type import series_is_nan


@add_input_table
class ControlsInputTable(InputTable):

    def __init__(self: typing.Self):
        super().__init__(
            sql_mapping=VehicleControls,
            columns=[
                InputColumn.from_data_column(
                    column=VehiclesModel.plate_number,
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=VehicleMaintenanceModel.computed_control_date,
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=VehicleMaintenanceModel.effective_control_date,
                    sql_name='effective_service_date',
                ),
                InputColumn.from_data_column(
                    column=VehicleMaintenanceModel.scheduled_control_date,
                ),
                InputColumn.from_data_column(
                    column=VehicleMaintenanceModel.maintenance_type,
                    sql_name='control_type',
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
        """ Get vehicle_services table

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

        combined_df = self.fill_missing_cols(combined_df)
        return combined_df.loc[
            ~series_is_nan(combined_df[VehiclesModel.plate_number.name])
            &
            ~series_is_nan(combined_df[VehicleMaintenanceModel.computed_control_date.name]),
            self.return_column_names()
        ]

    def to_sql(
        self: typing.Self,
        data_df: pd.DataFrame,
        organization_id: str,
        session: sa.orm.Session,
        logger: logging.Logger,
        update_values: str = 'null_only',
        columns: typing.List[str] = None,
    ) -> pd.DataFrame:
        """ Push new services to the database

        :param connector_data: connector Data Class with all folders
        """
        service_query = sa.select(
            VehicleControls.id,
            VehiclesTable.plate_number,
            VehicleControls.effective_control_date.label(
                'db_effective_control_date'
            ),
            VehicleControls.scheduled_control_date.label(
                'db_scheduled_control_date'
            ),
            VehicleControls.computed_control_date.label(
                'db_computed_control_date'
            ),
        ).select_from(
            VehicleControls
        ).join(
            VehiclesTable,
            VehicleControls.vehicle_id == VehiclesTable.id,
        ).filter(
            VehicleControls.organization_id == organization_id
        )

        db_df = pd.read_sql(
            service_query,
            session.bind,
        )

        computed_date_only = (
            db_df['db_effective_control_date'].isna()
            &
            db_df['db_scheduled_control_date'].isna()
        )

        computed_only = db_df[
            computed_date_only
        ]

        # Delete these from db
        delete_query = sa.delete(
            VehicleControls
        ).where(
            VehicleControls.id.in_(computed_only['id'])
        )
        session.execute(delete_query)

        # Do not update those already with a scheduled or effective date
        data_df = data_df[
            ~data_df[VehiclesModel.plate_number.name].isin(
                db_df.loc[
                    ~computed_date_only,
                    VehiclesModel.plate_number.name
                ].unique()
            )
        ]

        super().to_sql(
            data_df=data_df,
            organization_id=organization_id,
            session=session,
            logger=logger,
            update_values=update_values,
            columns=columns,
        )

        session.execute(
            sa.text('refresh materialized view publ.controls_view;')
        )

        session.commit()

        return data_df


if __name__ == "__main__":

    logger = gen_logger('controls_table')
    organization_name = 'acorus'
    organization_folder = os.path.join(
        os.environ['_soongo_data_folder'],
        organization_name,
    )
    connector_data = ConnectorData(
        root_folder=os.environ['_soongo_data_folder'],
        organization_name=organization_name,
    )
    service_table = ControlsInputTable()
    service_df = service_table.get(
        connector_data=connector_data,
        logger=logger,
    )
    service_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{service_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
