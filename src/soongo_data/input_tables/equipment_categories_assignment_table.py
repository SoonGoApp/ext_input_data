""" Script to calculate the equipment table."""
import logging
import os
import typing

import pandas as pd

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import EquipmentsModel, SoonGoRecordsModel
from soongo_data.sql_mappings import EquipmentCategoriesAssignmentTable
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id)
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.type import series_is_nan


@add_input_table
class EquipmentCategoriesAssignmentInputTable(InputTable):

    def __init__(self: typing.Self):
        super().__init__(
            sql_mapping=EquipmentCategoriesAssignmentTable,
            columns=[
                InputColumn.from_data_column(
                    column=EquipmentsModel.equipment_reference,
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=EquipmentsModel.equipment_category,
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
        combined_df = combined_df.loc[
            ~series_is_nan(
                combined_df[EquipmentsModel.equipment_reference.name]
            ),
        ]

        # Regroup based on id
        combined_df = self.rebuild_from_id(
            dup_df=combined_df,
            id_col=EquipmentsModel.equipment_reference.name,
            logger=logger,
        ).reset_index(drop=True)

        # Explode equipment_category
        combined_df[EquipmentsModel.equipment_category.name] = (
            combined_df[EquipmentsModel.equipment_category.name].str.split(', ')
        )
        combined_df = combined_df.explode(
            EquipmentsModel.equipment_category.name
        )

        return combined_df[self.return_column_names()]

    @staticmethod
    def rebuild_from_id(
        dup_df: pd.DataFrame,
        id_col: str,
        logger: logging.Logger,
    ) -> pd.DataFrame:
        """ Rebuild a DataFrame from an id col as a deduplication method

        :param dup_df: duplicated dataframe
        :param id_col: string name of the column to use as id

        :return: deduplicated column id.
        """
        initial_rows = len(dup_df)
        initial_ids = set(dup_df[id_col])

        missing_id = series_is_nan(dup_df[id_col])
        missing_id_df = dup_df.loc[missing_id,]
        id_df = dup_df.loc[~missing_id]
        dedup_df = id_df[[id_col]].drop_duplicates()
        for var_col in id_df.columns:
            if var_col == id_col:
                continue

            col_df = id_df.loc[
                ~series_is_nan(id_df[var_col]),
                [id_col, var_col]
            ].drop_duplicates(subset=id_col)  # Effectively keeps first entry

            dedup_df = dedup_df.merge(
                right=col_df,
                how='left',
                on=id_col,
                validate='1:1',
            )

        dedup_df = pd.concat([missing_id_df, dedup_df], axis=0)

        assert set(dedup_df[id_col]) == initial_ids
        assert (dedup_df.columns == dup_df.columns).all()
        logger.info(
            'Deduplicated %d equipment rows using column %s',
            initial_rows - len(dedup_df),
            id_col,
        )
        return dedup_df


if __name__ == "__main__":

    logger = gen_logger('employees_table')
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
    equipment_table = EquipmentCategoriesAssignmentInputTable()
    equipment_df = equipment_table.get(
        connector_data=connector_data,
        logger=logger,
    )
    equipment_table.check_columns(
        data_df=equipment_df,
        logger=logger,
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
