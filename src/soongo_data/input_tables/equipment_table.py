""" Script to calculate the equipment table."""
import logging
import os
import typing

import pandas as pd

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (BusinessUnitsModel, CollaboratorsModel,
                                     EquipmentsModel, SoonGoRecordsModel,
                                     VehiclesModel)
from soongo_data.input_tables.employees_table import EmployeesInputTable
from soongo_data.input_tables.vehicles_table import VehiclesInputTable
from soongo_data.sql_mappings import EquipmentTable
from soongo_data.utils.bu import get_business_units
from soongo_data.utils.enums import EquipmentStatus, Suppliers
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id,
                                            match_soongo_employee_id)
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.type import series_is_nan


@add_input_table
class EquipmentsInputTable(InputTable):

    def __init__(self: typing.Self):
        super().__init__(
            sql_mapping=EquipmentTable,
            columns=[
                InputColumn.from_data_column(
                    column=EquipmentsModel.equipment_reference,
                    unique=True,
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=EquipmentsModel.equipment_status,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=EquipmentsModel.equipment_supplier,
                    enum=Suppliers,
                ),
                InputColumn.from_data_column(
                    column=EquipmentsModel.equipment_product,
                    sql_name='product',
                ),
                InputColumn.from_data_column(
                    column=EquipmentsModel.equipment_start_date,
                ),
                InputColumn.from_data_column(
                    column=EquipmentsModel.equipment_end_date,
                ),
                InputColumn.from_data_column(
                    column=EquipmentsModel.equipment_code,
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.plate_number,
                    foreign_relationship=(
                        VehiclesInputTable().name,
                        VehiclesModel.plate_number.name,
                    ),
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
                    column=EquipmentsModel.equipment_type,
                    sql_name='type',
                ),
            ]
        )

    def _get_df(
        self: typing.Self,
        connector_data: ConnectorData,
        logger: logging.Logger,
        fetch_params_dict: typing.Optional[dict] = None,
    ) -> pd.DataFrame:
        """ Get equipments table

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

        combined_df = get_business_units(
            combined_df,
            logger=logger,
            organization_name=connector_data.organization_name,
        )
        combined_df = match_soongo_employee_id(
            table_to_match=combined_df,
            organization_name=connector_data.organization_name,
        )
        # Regroup based on id
        combined_df = self.regroup_df(
            dup_df=combined_df,
            id_cols=[EquipmentsModel.equipment_reference.name],
            logger=logger,
        ).reset_index(drop=True)

        combined_df = self.fill_missing_cols(combined_df)
        combined_df[EquipmentsModel.equipment_status.name] = (
            combined_df[EquipmentsModel.equipment_status.name].mask(
                series_is_nan(combined_df[EquipmentsModel.equipment_status.name]),
                EquipmentStatus.unknown.value
            )
        )

        return combined_df.loc[
            ~series_is_nan(combined_df[EquipmentsModel.equipment_reference.name]),
            self.return_column_names()
        ]


if __name__ == "__main__":

    logger = gen_logger('equipments_table')
    organization_name = 'quartus'
    organization_folder = os.path.join(
        os.environ['_soongo_data_folder'],
        organization_name,
    )
    connector_data = ConnectorData(
        root_folder=os.environ['_soongo_data_folder'],
        organization_name=organization_name,
    )
    equipment_table = EquipmentsInputTable()
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
        vehicles=VehiclesInputTable().get(
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
