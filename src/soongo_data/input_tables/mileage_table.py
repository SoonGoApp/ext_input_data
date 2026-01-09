""" Script to calculate the mileage table to load in database."""
import logging
import math
import os
import typing

import numpy as np
import pandas as pd
from sqlalchemy import UUID, text, select
from sqlalchemy.orm import Session

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (MileageReportsModel, SoonGoRecordsModel,
                                     VehiclesModel)
from soongo_data.input_tables.vehicles_table import VehiclesInputTable
from soongo_data.sql_mappings import (
    MileagesTable, SynchronisationsTable, ConnectorsTable, SuppliersTable,
    VehiclesTable
)
from soongo_data.utils.enums import SuppliersType
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id)
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.uploads import fetch_db_data
from soongo_data.utils.type import series_is_nan


@add_input_table
class MileagesInputTable(InputTable):

    def __init__(self):
        super().__init__(
            sql_mapping=MileagesTable,
            date_col_name='mileage_date',
            columns=[
                InputColumn.from_data_column(
                    column=VehiclesModel.plate_number,
                    foreign_relationship=(
                        VehiclesInputTable().name,
                        VehiclesModel.plate_number.name,
                    ),
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=MileageReportsModel.mileage,
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=MileageReportsModel.mileage_date,
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
            ],
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
        # Aggregate data
        combined_df = self.fetch_table_data(
            connector_data=connector_data,
            logger=logger,
            fetch_params_dict=fetch_params_dict,
        )
        combined_df = add_synchronization_id(combined_df, connector_data)
        if combined_df.empty:
            return combined_df

        combined_df = combined_df.loc[
            ~series_is_nan(combined_df[VehiclesModel.plate_number.name]) &
            ~series_is_nan(combined_df[MileageReportsModel.mileage.name]) &
            ~series_is_nan(combined_df[MileageReportsModel.mileage_date.name]),
        ]

        combined_df = self.correct_inconsistent_mileage(
            mileage_df=combined_df,
            _logger=logger,
        )
        tz = combined_df[MileageReportsModel.mileage_date.name].dt.tz
        now = pd.Timestamp.now(tz=tz)
        is_future = combined_df[MileageReportsModel.mileage_date.name] > now
        if is_future.any():
            logger.warning(
                'Dropping %d mileage readings because they are in the future',
                np.sum(is_future),
            )
            combined_df = combined_df.loc[~is_future, ]

        self.df = combined_df[self.return_column_names()]
        return self.df

    @staticmethod
    def correct_inconsistent_mileage(
        mileage_df: pd.DataFrame,
        _logger: logging.Logger,
        max_mileage_per_day: int = 1000,
        max_mileage_per_week: int = 5000,
    ) -> pd.DataFrame:
        """ Correct inconsistent mileage values - i.e. lower mileage at more
        recent datetime

        :param mileage_df: Pandas Dataframe with plate_number, mileage, date
        """
        # Inefficient solution - loop across rows
        plate_col = VehiclesModel.plate_number.name
        mileage_col = MileageReportsModel.mileage.name
        date_col = MileageReportsModel.mileage_date.name
        mileage_df = mileage_df.sort_values(
            by=[plate_col, date_col, mileage_col],
        )
        error_vec = np.repeat([0], repeats=len(mileage_df))
        mileage_df.reset_index(drop=True, inplace=True)
        previous_row = mileage_df.iloc[0, :]
        for index, row in mileage_df.iterrows():
            error = False
            if (
                (row[mileage_col] < previous_row[mileage_col]) &
                (row[plate_col] == previous_row[plate_col]) &
                pd.notna(row[date_col]) &
                pd.notna(previous_row[date_col])
            ):
                error_vec[index] = 1
                error = True

            if (
                (row[plate_col] == previous_row[plate_col]) &
                pd.notna(row[date_col]) &
                pd.notna(previous_row[date_col])
            ):
                day_diff = (row[date_col] - previous_row[date_col]).days
                mileage_diff = row[mileage_col] - previous_row[mileage_col]

                if day_diff > 0:
                    mileage_per_day = mileage_diff / day_diff
                    week_count = math.ceil(day_diff / 7)
                    is_error = (
                        (mileage_per_day > max_mileage_per_day)
                        or (mileage_diff > week_count * max_mileage_per_week)
                    )

                else:  # If the two readings occured on the same day
                    is_error = mileage_diff > max_mileage_per_day

                if is_error:
                    error_vec[index] = 1
                    error = True

            if not error:
                previous_row = row

        _logger.info(
            'Dropping %d mileage readings because inconsistent with previous '
            'readings',
            np.sum(error_vec)
        )

        mileage_df = mileage_df.loc[error_vec != 1, ]

        return mileage_df

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
        data_df = self.filter_non_telematics_for_telematic_vehicles(
            data_df=data_df,
            session=session,
            logger=logger,
            organization_id=organization_id,
        )

        data_df = self.filter_measures_inconsistent_with_db(
            data_df=data_df,
            session=session,
            id_cols=self.get_id_cols(),
            organization_id=organization_id,
            logger=logger,
        )

        super().to_sql(
            data_df=data_df,
            organization_id=organization_id,
            session=session,
            logger=logger,
            update_values=update_values,
            columns=columns,
        )

        session.execute(
            text("select graphile_worker.add_job('refresh_materialized_view', json_build_object('view', 'publ.mileage_primitive_view'));"),
        )

    @staticmethod
    def filter_non_telematics_for_telematic_vehicles(
        organization_id: UUID,
        data_df: pd.DataFrame,
        session: Session,
        logger: logging.Logger,
    ) -> pd.DataFrame:
        """
        Do not insert non telematics mileage readings for vehicles that have
        telematics mileage readings.

        :param data_df: Dataframe with mileage readings to be inserted
        :param session: SQLAlchemy session
        :param logger: Logger

        :return: Filtered dataframe
        """
        telematic_plates_query = select(
            VehiclesTable.plate_number
        ).select_from(
            MileagesTable
        ).join(
            VehiclesTable,
            VehiclesTable.id == MileagesTable.vehicle_id
        ).join(
            SynchronisationsTable,
            SynchronisationsTable.id == MileagesTable.synchronisation_id
        ).join(
            ConnectorsTable,
            ConnectorsTable.id == SynchronisationsTable.connector_id
        ).join(
            SuppliersTable,
            SuppliersTable.name == ConnectorsTable.name
        ).where(
            SuppliersTable.type == SuppliersType.telematics.value,
            MileagesTable.organization_id == organization_id,
        ).group_by(
            VehiclesTable.plate_number
        )

        telematic_plates_df = pd.read_sql(
            telematic_plates_query,
            session.get_bind(),
        )

        telematics_suppliers = session.execute(
            select(SuppliersTable.name).where(
                SuppliersTable.type == SuppliersType.telematics.value
            )
        ).scalars().all()

        data_df = data_df.merge(
            telematic_plates_df,
            how='left',
            on=VehiclesModel.plate_number.name,
            indicator='_has_telematics',
        )
        to_drop = (
            (data_df['_has_telematics'] == 'both')
            &
            (~data_df[SoonGoRecordsModel.connector_name.name].isin(telematics_suppliers))
        )
        if to_drop.any():
            logger.info(
                'Dropping %d non telematics mileage readings for vehicles '
                'that have telematics mileage readings',
                np.sum(to_drop),
            )
            data_df = data_df[~to_drop]

        data_df = data_df.drop(columns=['_has_telematics'])

        return data_df

    def filter_measures_inconsistent_with_db(
        self,
        data_df: pd.DataFrame,
        session: Session,
        id_cols: dict,
        organization_id: UUID,
        logger: logging.Logger,
    ) -> pd.DataFrame:
        """ Filter out wrong mileage measures"""
        # Filter out wrong mileage measures
        start_date = data_df[self.date_col_name].min()
        end_date = data_df[self.date_col_name].max()

        db_df = fetch_db_data(
            sql_mapping=self.sql_mapping,
            id_cols=id_cols,
            engine=session.get_bind(),
            logger=logger,
            organization_id=organization_id,
            date_col_name=self.date_col_name,
            start_date=start_date,
            end_date=end_date,
        )
        for col_name in db_df.columns:
            col_series = db_df[col_name]
            if pd.api.types.is_datetime64_any_dtype(col_series):
                db_df[col_name] = col_series.dt.tz_localize(None)

        db_df['is_original'] = False
        data_df['is_original'] = True
        combined_df = pd.concat([db_df, data_df], ignore_index=True)
        combined_df = self.correct_inconsistent_mileage(
            mileage_df=combined_df,
            _logger=logger,
        )
        return combined_df.loc[
            combined_df['is_original'],
            self.return_column_names()
        ]


if __name__ == "__main__":
    logger = gen_logger('mileage_table')
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
    mileage_table = MileagesInputTable()
    mileage_df = mileage_table.get(
        connector_data=connector_data,
        logger=logger,
    )
    mileage_table.check_columns(
        data_df=mileage_df,
        vehicles=VehiclesInputTable().get(
            connector_data=connector_data,
            logger=logger,
        ),
        logger=logger,
    )
    mileage_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{mileage_table.name}_table.csv',
        ),
        index=False,
        sep=';',
        date_format=r'%Y-%m-%d %H:%M:%S',
    )
