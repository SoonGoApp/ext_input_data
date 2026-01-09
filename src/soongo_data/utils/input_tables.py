""" Table script utility functions"""
from itertools import zip_longest
import logging
from operator import itemgetter
import os
import re
import typing
import warnings
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Self, Set, Tuple, Union
from uuid import UUID

import pandas as pd
import sqlalchemy as sa
import yaml
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm.session import Session

from soongo_data.connectors import (
    Dataset,
    ConnectorData,
    check_no_dup_values)
from soongo_data.data_models import (AccidentsModel, BusinessUnitsModel, CollaboratorsModel,
                                     EquipmentsModel, ExpensesModel,
                                     SoonGoRecordsModel, SuppliersModel,
                                     VehicleAssociationsModel, VehiclesModel)
from soongo_data.data_models.base import DataColumn
from soongo_data.sql_mappings import (CollaboratorsTable, EquipmentTable,
                                      OrganizationParametersTable,
                                      OrganizationsTable,
                                      VehicleAttributionsTable, VehiclesTable)
from soongo_data.utils.db import gen_engine
from soongo_data.utils.enums import EquipmentStatus
from soongo_data.utils.type import (NamesConverter, get_dtype_null,
                                    series_is_nan, str_is_nan)
from soongo_data.utils.uploads import (BusinessUnitInserter, RegionInserter,
                                       SynchronisationInserter, TrimInserter,
                                       SupplierInserter, fetch_connector_ids,
                                       fetch_accident_ids,
                                       insert_sliding_table, upsert_table)

# Suppress the specific warning
warnings.filterwarnings("ignore", message="Workbook contains no default style, apply openpyxl's default")


@dataclass
class InputColumn(DataColumn):

    format: Optional[re.Pattern] = None
    foreign_relationship: Tuple[str, str] = tuple()
    unique: bool = False
    nullable: bool = True
    enum: Optional[Enum] = None
    default: Any = None
    # Whether the column should be taken into account to recognized updates
    is_id: bool = False
    # Sliding window column. Start or end of date cols, or update
    sliding_col: Optional[str] = None
    sql_name: str = None  # None replaced with str in post_init

    @staticmethod
    def from_data_column(
        column: DataColumn,
        **input_col_kwargs,
    ) -> Self:
        """ Generate an InputColumn object from a Data Column

        :param column: a DataColumn instance
        **input_col_kwargs: a foreign_relationship, unique, or nullable value
        """
        return InputColumn(
            **asdict(column),
            **input_col_kwargs,
        )

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, InputColumn):
            return self.name == other.name
        else:
            return False

    def __post_init__(self):
        if self.sql_name is None:
            self.sql_name = self.name
        return super().__post_init__()


class InputTable(ABC):

    def __init__(
        self,
        sql_mapping: DeclarativeMeta,
        columns: List[InputColumn],
        date_col_name: typing.Optional[str] = None,
    ) -> None:
        self.name = sql_mapping.__tablename__
        self.columns = columns
        self.sql_mapping = sql_mapping
        self.date_col_name = date_col_name
        self.df = None  # Memoization

    def get(
        self: typing.Self,
        connector_data: ConnectorData,
        logger: logging.Logger,
        fetch_params_dict: typing.Optional[dict] = None,
    ) -> pd.DataFrame:
        """ Getter function implementing memorization to avoid recalculating
        the dataframe at every get
        """
        return self._get_df(
            connector_data=connector_data,
            logger=logger,
            fetch_params_dict=fetch_params_dict,
        )

    @abstractmethod
    def _get_df(
        self: typing.Self,
        connector_data: ConnectorData,
        logger: logging.Logger,
        fetch_params_dict: typing.Optional[dict] = None,
    ) -> pd.DataFrame:
        """ Underlying method calculating an input DataFrame from the connector
        source data, given fetch_params_dictionnary.

        """
        raise NotImplementedError('Abstract get method must be implemented')

    def to_sql(
        self: typing.Self,
        data_df: pd.DataFrame,
        organization_id: UUID,
        session: Session,
        logger: logging.Logger,
        update_values: str = 'null_only',
        columns: List[str] = None,
    ) -> pd.DataFrame:
        """ Inserts the passed data_df to the input_table db table mapping

        :param data_df: a dataframe containing the data to be uploaded to SQL
        :param organization_id: a db valid organization uuid
        :param session: a SQLAlchemy session
        :param logger: logging.Logger
        :param update_values: 'overwrite', 'keep', or null_only to determine
            how to handle existing rows in the db
        :param columns: columns to update
        """
        if columns is None:
            columns = []

        if not organization_id:
            raise ValueError(
                'The argument organization_id cannot be null'
            )
        data_df[SoonGoRecordsModel.organization_id.name] = organization_id
        sql_columns = [column.name for column in self.sql_mapping.__table__.columns]
        data_df = data_df.rename(
            columns={
                column.name: column.sql_name
                for column in self.columns
            }
        )
        id_cols = self.get_id_cols()

        # First handle connector ids
        logger.info('Handling foreign key references')
        if (SoonGoRecordsModel.connector_name.name in data_df.columns):

            if SoonGoRecordsModel.connector_id.name not in data_df:

                data_df = fetch_connector_ids(
                    data_df=data_df,
                    session=session,
                )

            if SoonGoRecordsModel.connector_name.name in id_cols:
                connector_col = id_cols.pop(
                    SoonGoRecordsModel.connector_name.name
                )
                id_cols[SoonGoRecordsModel.connector_id.name] = InputColumn.from_data_column(
                    SoonGoRecordsModel.connector_id,
                    nullable=connector_col.nullable,
                )

            if (
                (SoonGoRecordsModel.connector_name.name in columns)
                and
                (SoonGoRecordsModel.connector_id.name in sql_columns)
            ):
                columns.remove(SoonGoRecordsModel.connector_name.name)
                columns.append(SoonGoRecordsModel.connector_id.name)

        if SoonGoRecordsModel.synchronisation_id.name in data_df.columns:
            data_df = SynchronisationInserter(session, organization_id).insert_df(data_df)

        # Then handle other foreign key references
        if (
            (VehiclesModel.plate_number.name in data_df.columns) and
            (VehiclesModel.vehicle_id.name in self.sql_mapping.__table__.columns)
        ):

            if VehiclesModel.vehicle_id.name not in data_df:
                vehicle_input_table = input_table_dict[VehiclesTable.__tablename__]
                ids_df = upsert_table(
                    input_table=vehicle_input_table,
                    insert_df=data_df,
                    logger=logger,
                    session=session,
                    organization_id=organization_id,
                    deduplicate_values=True,  # Vehicles duplicated in expenses and the like
                    update_values='keep',
                ).rename(columns={'id': VehiclesModel.vehicle_id.name})
                data_df = data_df.merge(
                    right=ids_df,
                    on=list(vehicle_input_table.get_id_cols().keys()),
                    how='left',
                    validate='m:1',
                )

            if VehiclesModel.plate_number.name in id_cols:
                vehicle_col = id_cols.pop(
                    VehiclesModel.plate_number.name
                )
                id_cols[VehiclesModel.vehicle_id.name] = InputColumn.from_data_column(
                    VehiclesModel.vehicle_id,
                    nullable=vehicle_col.nullable,
                )

            if (
                (VehiclesModel.plate_number.name in columns)
                and
                (VehiclesModel.vehicle_id.name in sql_columns)
            ):
                columns.remove(VehiclesModel.plate_number.name)
                columns.append(VehiclesModel.vehicle_id.name)

        if (
            (CollaboratorsModel.soongo_collab_reference.name in data_df.columns)
            and
            (CollaboratorsModel.collaborator_id.name in self.sql_mapping.__table__.columns)
        ):

            if CollaboratorsModel.collaborator_id.name not in data_df:
                collaborator_input_table = input_table_dict[CollaboratorsTable.__tablename__]
                ids_df = upsert_table(
                    input_table=collaborator_input_table,
                    insert_df=data_df,
                    logger=logger,
                    session=session,
                    organization_id=organization_id,
                    deduplicate_values=True,  # Vehicles duplicated in expenses and the like
                    update_values='keep',
                ).rename(columns={'id': CollaboratorsModel.collaborator_id.name})

                data_df = data_df.merge(
                    right=ids_df,
                    on=list(collaborator_input_table.get_id_cols().keys()),
                    how='left',
                    validate='m:1',
                )

            if CollaboratorsModel.soongo_collab_reference.name in id_cols:
                collab_col = id_cols.pop(
                    CollaboratorsModel.soongo_collab_reference.name
                )
                id_cols[CollaboratorsModel.collaborator_id.name] = InputColumn.from_data_column(
                    CollaboratorsModel.collaborator_id,
                    nullable=collab_col.nullable,
                )

            if (
                (CollaboratorsModel.soongo_collab_reference.name in columns)
                and
                (CollaboratorsModel.collaborator_id.name in sql_columns)
            ):
                columns.remove(CollaboratorsModel.soongo_collab_reference.name)
                columns.append(CollaboratorsModel.collaborator_id.name)

        if (
            (EquipmentsModel.equipment_reference.name in data_df.columns)
            and
            (EquipmentsModel.equipment_id.name in self.sql_mapping.__table__.columns)
        ):

            if EquipmentsModel.equipment_id.name not in data_df:
                if EquipmentsModel.equipment_status.name in data_df:
                    data_df[EquipmentsModel.equipment_status.name] = (
                        data_df[EquipmentsModel.equipment_status.name].fillna(
                            EquipmentStatus.unknown.value
                        )
                    )
                else:
                    data_df[EquipmentsModel.equipment_status.name] = (
                        EquipmentStatus.unknown.value
                    )

                equipment_input_table = input_table_dict[EquipmentTable.__tablename__]
                ids_df = upsert_table(
                    input_table=equipment_input_table,
                    insert_df=data_df,
                    logger=logger,
                    session=session,
                    organization_id=organization_id,
                    deduplicate_values=True,  # Vehicles duplicated in expenses and the like
                    update_values='keep',
                ).rename(columns={'id': EquipmentsModel.equipment_id.name})

                data_df = data_df.merge(
                    right=ids_df,
                    on=list(equipment_input_table.get_id_cols().keys()),
                    how='left',
                    validate='m:1',
                )

            if EquipmentsModel.equipment_reference.name in id_cols:
                connector_col = id_cols.pop(
                    EquipmentsModel.equipment_reference.name
                )
                id_cols[EquipmentsModel.equipment_id.name] = InputColumn.from_data_column(
                    EquipmentsModel.equipment_id,
                    nullable=connector_col.nullable,
                )

            if (
                (EquipmentsModel.equipment_reference.name in columns)
                and
                (EquipmentsModel.equipment_id.name in sql_columns)
            ):
                columns.remove(EquipmentsModel.equipment_reference.name)
                columns.append(EquipmentsModel.equipment_id.name)

        if (
            (AccidentsModel.accident_ref.name in data_df.columns)
            and
            (AccidentsModel.accident_id.name in self.sql_mapping.__table__.columns)
        ):

            if AccidentsModel.accident_id.name not in data_df:

                data_df = fetch_accident_ids(
                    data_df=data_df,
                    session=session,
                    organization_id=organization_id,
                )

            if AccidentsModel.accident_ref.name in id_cols:
                connector_col = id_cols.pop(
                    AccidentsModel.accident_ref.name
                )
                id_cols[AccidentsModel.accident_id.name] = InputColumn.from_data_column(
                    AccidentsModel.accident_id,
                    nullable=connector_col.nullable,
                )

            if (
                (AccidentsModel.accident_ref.name in columns)
                and
                (AccidentsModel.accident_id.name in sql_columns)
            ):
                columns.remove(AccidentsModel.accident_ref.name)
                columns.append(AccidentsModel.accident_id.name)

        if (
            (BusinessUnitsModel.business_unit.name in data_df.columns)
            and
            (BusinessUnitsModel.business_unit_id.name in self.sql_mapping.__table__.columns)
        ):
            data_df = BusinessUnitInserter(session, organization_id).insert_df(data_df)

            if BusinessUnitsModel.business_unit.name in id_cols:
                connector_col = id_cols.pop(
                    BusinessUnitsModel.business_unit.name
                )
                id_cols[BusinessUnitsModel.business_unit_id.name] = InputColumn.from_data_column(
                    BusinessUnitsModel.business_unit_id,
                    nullable=connector_col.nullable,
                )

            if (
                (BusinessUnitsModel.business_unit.name in columns)
                and
                (BusinessUnitsModel.business_unit_id.name in sql_columns)
            ):
                columns.remove(BusinessUnitsModel.business_unit.name)
                columns.append(BusinessUnitsModel.business_unit_id.name)

        if (
            (BusinessUnitsModel.geography.name in data_df.columns)
            and
            (BusinessUnitsModel.region_id.name in self.sql_mapping.__table__.columns)
        ):
            data_df = RegionInserter(session, organization_id).insert_df(data_df)

            if BusinessUnitsModel.geography.name in id_cols:
                connector_col = id_cols.pop(
                    BusinessUnitsModel.geography.name
                )
                id_cols[BusinessUnitsModel.region_id.name] = InputColumn.from_data_column(
                    BusinessUnitsModel.region_id,
                    nullable=connector_col.nullable,
                )

            if (
                (BusinessUnitsModel.geography.name in columns)
                and
                (BusinessUnitsModel.region_id.name in sql_columns)
            ):
                columns.remove(BusinessUnitsModel.geography.name)
                columns.append(BusinessUnitsModel.region_id.name)

        if (
            (VehiclesModel.full_model.name in data_df.columns)
            and
            (VehiclesModel.trim_id.name in self.sql_mapping.__table__.columns)
        ):
            data_df = TrimInserter(session, organization_id).insert_df(data_df)

            for foreign_key_tup in [
                (VehiclesModel.make.name, VehiclesModel.brand_id),
                (VehiclesModel.model.name, VehiclesModel.model_id),
                (VehiclesModel.full_model.name, VehiclesModel.trim_id),
            ]:
                if foreign_key_tup[0] in id_cols:
                    connector_col = id_cols.pop(foreign_key_tup[0])
                    id_cols[foreign_key_tup[1].name] = InputColumn.from_data_column(
                        foreign_key_tup[1],
                        nullable=connector_col.nullable,
                    )

                if (
                    (foreign_key_tup[0] in columns)
                    and
                    (foreign_key_tup[1].name in sql_columns)
                ):
                    columns.remove(foreign_key_tup[0])
                    columns.append(foreign_key_tup[1].name)

        supplier_cols = {
            EquipmentsModel.equipment_supplier.name,
            VehiclesModel.car_supplier.name,
            ExpensesModel.supplier.name,
        }.intersection(data_df.columns)
        if (
            supplier_cols
            and
            (SuppliersModel.supplier_id.name in self.sql_mapping.__table__.columns)
        ):
            assert len(supplier_cols) == 1, 'Cannot have multiple supplier columns'
            supplier_col_name = supplier_cols.pop()

            if SuppliersModel.supplier_id.name not in data_df:

                supplier_inserter = SupplierInserter(
                    session=session,
                    organization_id=organization_id,
                    supplier_col=supplier_col_name,
                )
                data_df = supplier_inserter.insert_df(
                    data_df=data_df
                )

            if supplier_col_name in id_cols:
                supplier_col = id_cols.pop(
                    supplier_col_name
                )
                id_cols[SuppliersModel.supplier_id.name] = InputColumn.from_data_column(
                    SuppliersModel.supplier_id,
                    nullable=supplier_col.nullable,
                )

            if (
                (supplier_col_name in columns)
                and
                (SuppliersModel.supplier_id.name in sql_columns)
            ):
                columns.remove(supplier_col_name)
                columns.append(SuppliersModel.supplier_id.name)

        if (
            VehicleAssociationsModel.assigned_service.name in data_df.columns
            and
            (BusinessUnitsModel.business_unit_id.name in self.sql_mapping.__table__.columns)
        ):
            BusinessUnitsModel.business_unit.name not in data_df.columns, 'Cannot have multiple bu columns'

            if BusinessUnitsModel.business_unit_id.name not in data_df:

                data_df = BusinessUnitInserter(
                    session=session,
                    organization_id=organization_id,
                    matching_col=VehicleAssociationsModel.assigned_service.name,
                ).insert_df(data_df=data_df)

            if VehicleAssociationsModel.assigned_service.name in id_cols:
                bu_col = id_cols.pop(
                    VehicleAssociationsModel.assigned_service.name
                )
                id_cols[BusinessUnitsModel.business_unit_id.name] = InputColumn.from_data_column(
                    BusinessUnitsModel.business_unit_id,
                    nullable=bu_col.nullable,
                )

            if (
                (VehicleAssociationsModel.assigned_service.name in columns)
                and
                (BusinessUnitsModel.business_unit_id.name in sql_columns)
            ):
                columns.remove(VehicleAssociationsModel.assigned_service.name)
                columns.append(BusinessUnitsModel.business_unit_id.name)

        logger.info('Handled recursive foreign keys')

        if SoonGoRecordsModel.synchronisation_id.name in data_df.columns:
            logger.info(
                'Upserting %d rows in the %s table from synchronizations %s',
                len(data_df),
                self.sql_mapping.__tablename__,
                data_df[SoonGoRecordsModel.synchronisation_id.name].unique().tolist()
            )
        else:
            logger.info(
                'Upserting %d rows in the %s table',
                len(data_df),
                self.sql_mapping.__tablename__,
            )

        sliding_date_cols = self.get_sliding_dates()
        if sliding_date_cols:
            update_cols = self.get_sliding_update_cols()
            if update_cols is None:
                raise ValueError(
                    'Need to provide update columns for sliding table to '
                    'determine when to insert data in the sliding table'
                )
            insert_sliding_table(
                input_table=self,
                insert_df=data_df,
                id_cols=id_cols,
                logger=logger,
                session=session,
                organization_id=organization_id,
                start_col=sliding_date_cols['start'],
                end_col=sliding_date_cols['end'],
                update_values=update_values,
                columns=columns,
                update_cols=update_cols,
            )
        else:
            upsert_table(
                input_table=self,
                insert_df=data_df,
                id_cols=id_cols,
                logger=logger,
                session=session,
                organization_id=organization_id,
                deduplicate_values=False,  # Data as is
                update_values=update_values,
                columns=columns,
            )

    def check_columns(
        self,
        data_df: pd.DataFrame,
        logger: logging.Logger,
        **source_tables,
    ):
        """ Check the DataFrame columns based on the InputColumn instances

        :param data_df: the dataframe of data to check
        :param logger: logger
        **source_tables: table_name as argument name and dataframe as argument
        value for all source tables

        :raises ValueError: if any column is missing, does not match
            expected type, nullability, format, unicity, or foreign constraint
        """
        if len(self.columns) != len(data_df.columns):
            missing_columns = set(self.columns).difference(data_df.columns)
            extra_columns = set(data_df.columns).difference(self.columns)
            raise ValueError(
                f'There are {len(missing_columns)} in the dataframe: '
                f'{missing_columns} and {len(extra_columns)} unexpected '
                f'columns: {extra_columns}'
            )

        check_no_dup_values(data_df.columns)

        for column in self.columns:

            if column.name not in data_df:
                raise ValueError(
                    f"Column '{column.name}' not found in the CSV file."
                )

            # Define null values
            col_series = data_df[column.name]
            if (
                (
                    pd.api.types.is_integer_dtype(col_series.dtype) !=
                    pd.api.types.is_integer_dtype(column.dtype)
                ) |
                (
                    pd.api.types.is_string_dtype(col_series.dtype) !=
                    pd.api.types.is_string_dtype(column.dtype)
                ) |
                (
                    pd.api.types.is_float_dtype(col_series.dtype) !=
                    pd.api.types.is_float_dtype(column.dtype)
                ) |
                (
                    pd.api.types.is_bool_dtype(col_series.dtype) !=
                    pd.api.types.is_bool_dtype(column.dtype)
                ) |
                (
                    pd.api.types.is_datetime64_any_dtype(col_series.dtype) !=
                    pd.api.types.is_datetime64_any_dtype(column.dtype)
                )
            ):
                raise ValueError(
                    f"Column '{column.name}' has the wrong data type. "
                    f'Expected: {column.dtype}, '
                    f'Got: {col_series.dtype}.'
                )

            null_values = series_is_nan(col_series)
            if column.nullable:
                if null_values.all():
                    logger.error(
                        'Column %s is entirely composed of null values',
                        column.name,
                    )
            elif null_values.any():
                null_connectors = data_df.loc[
                    null_values,
                    SoonGoRecordsModel.connector_name.name
                ].unique().tolist()
                raise ValueError(
                    f"Column {column.name} contains {null_values.sum()} null"
                    f' values from connectors {null_connectors} whilst column'
                    f' is not nullable'
                )

            if column.format:
                format_not_ok = col_series.loc[
                    ~str_is_nan(col_series.astype(str))
                    & ~col_series.astype(str).str.match(column.format)
                ]
                if len(format_not_ok):
                    raise ValueError(
                        f"Column '{column.name}' contains "
                        f'{len(format_not_ok)} values that do not match '
                        f'the format: {column.format} '
                        f'for example: {format_not_ok.head(5)}'
                    )

            if column.unique and not col_series.loc[
                ~null_values
            ].is_unique:
                raise ValueError(
                    f"Column '{column.name}' contains duplicate values.: "
                    f'{col_series.loc[col_series.duplicated()].unique()}'
                )

            if column.foreign_relationship:
                self.check_foreign_relationship(
                    column_series=col_series,
                    column_definition=column,
                    source_tables=source_tables,
                )

            if column.enum:
                allowed_values = {member.value for member in column.enum}
                if not all({isinstance(val, str) for val in allowed_values}):
                    try:
                        # supplier case: enum is an object of name and other attributes
                        allowed_values = {val.name for val in allowed_values}
                    except AttributeError:
                        raise ValueError(
                            'Enum values must be strings or have a name attribute'
                        )
                self.check_allowed_values(
                    allowed_values=allowed_values,
                    col_to_check=col_series,
                )

        logger.info('Table %s matches all its requirements.', self.name)

    @classmethod
    def check_foreign_relationship(
        cls,
        column_series: pd.Series,
        column_definition: InputColumn,
        source_tables: Dict[str, pd.DataFrame],
    ):
        """ Check foreign relationship between the source tables and
        the current table.

        :param column_series: data column values as a pandas Series
        :param column_definition: DataColumn object
        :param source_tables: dictionary of table names to df

        :raise KeyError: if foreign table name not in source tables
        :raise ValueError: if unmatched values in column_series
        """
        if column_definition.foreign_relationship is None:
            return
        table_name, column_name = column_definition.foreign_relationship
        if table_name not in source_tables:
            raise KeyError(
                f'Table "{table_name}" was not provided in source tables:'
                f' {source_tables.keys()}'
            )
        source_values = set(source_tables[table_name][column_name].unique())
        cls.check_allowed_values(
            allowed_values=source_values,
            col_to_check=column_series,
        )

    @staticmethod
    def check_allowed_values(
        allowed_values: set,
        col_to_check: pd.Series,
    ) -> None:
        """ Check allowed values in a pandas Series

        :param allowed_values: set of values allowed in the Series
        :param col_to_check: Series whose value to check

        :raises ValueError: if the Series contains non null values not in
            allowed values
        """
        # TODO: clean fillnas, ignore null values for now
        unmatched_values = set(
            col_to_check.loc[~series_is_nan(col_to_check)].unique()
        ).difference(allowed_values)
        if unmatched_values:
            raise ValueError(
                f'There are {len(unmatched_values)} unmatched value in column'
                f' "{col_to_check.name}": {unmatched_values}'
            )

    def return_column_names(self) -> List[str]:
        return [col.name for col in self.columns]

    def get_id_cols(self: typing.Self) -> typing.Dict[str, InputColumn]:
        """ Get id column names, i.e. the name of the columns which will be used
        to uniquely identify entries on this table

        :param input_table: InputTable to insert data from

        :returns: list of column names to be used as ids
        """
        return {
            col.sql_name: col
            for col in self.columns if col.is_id
        }

    def get_sliding_dates(self) -> typing.Optional[typing.Dict[str, InputColumn]]:
        """ Get sliding column names, i.e. the name of the columns which will
        be used to define the sliding window on this table

        :returns: tuple of column names to be used as sliding window
        """
        sliding_cols = {
            col.sliding_col: col
            for col in self.columns
            if col.sliding_col in ('start', 'end')
        }
        if len(sliding_cols) == 2:
            return sliding_cols
        elif sliding_cols:
            raise ValueError(
                f'Table {self.name} sliding cols specification is incorrect: '
                f'one start, one end expected, but {sliding_cols} passed'
            )

        return None

    def get_sliding_update_cols(self) -> typing.Optional[typing.Collection[InputColumn]]:
        """ Get sliding column names, i.e. the name of the columns which will
        be used to define the sliding window on this table

        :returns: tuple of column names to be used as sliding window
        """
        return [
            col
            for col in self.columns
            if col.sliding_col == "update"
        ]

    def fetch_table_data(
        self: typing.Self,
        connector_data: ConnectorData,
        logger: logging.Logger,
        fetch_params_dict: typing.Optional[dict] = None,
    ) -> pd.DataFrame:
        """ Fetch the data necessary for the table, according to each organization
        configuration.

        :param connector_data: ConnectorData object with all the organization data
        :param logger: logger
        :param organization_name: name of the organization
        :param table: InputTable being built

        :returns: combined df with all required data
        """
        if not fetch_params_dict:
            fetch_params_dict = fetch_organization_params(
                connector_data.organization_name,
            )[self.name]['fetch_table_params']

        try:
            if fetch_params_dict.get('exclude_tables') == [['*', '*', '*']]:
                raise NoMatchedTable(
                    'All tables explicitly excluded from fetch'
                )
            return combine_connector_data(
                connector_data=connector_data,
                logger=logger,
                **fetch_params_dict,
            )
        except NoMatchedTable:
            logger.error(
                f'No {self.name} data, returning an empty DataFrame'
            )
            return pd.DataFrame(
                {
                    column.name: pd.Series(dtype=column.dtype)
                    for column in self.columns
                }
            )

    def fill_missing_cols(self: typing.Self, df: pd.DataFrame) -> pd.DataFrame:
        """ Fill in missing columns in a Dataframe to produce a given table

        :param df: pd.Dataframe to fill in
        :param table: InputTable to match
        """
        for col in self.columns:
            if col.name not in df.columns:
                if col.nullable is False:
                    raise ValueError(
                        f'Column {col.name} is missing from Dataframe whilst'
                        f' it is not nullable'
                    )

                df[col.name] = get_dtype_null(col.dtype)
                df[col.name] = df[col.name].astype(col.dtype)

            if col.default is not None:
                df[col.name] = df[col.name].fillna(
                    col.default,
                )

        return df

    @staticmethod
    def regroup_df(
        dup_df: pd.DataFrame,
        id_cols: typing.List[str],
        logger: logging.Logger,
    ) -> pd.DataFrame:
        """ Regroup df to get rid of duplicates

        :param dup_df: pd.DataFrame with duplicatee values for each id_cols
        :param id_cols: list of string column names which should be unique
        :param logger: logger

        :returns: dataframe with unique id_cols values. Conflicting non null
        values across the non id_cols set to null.
        """
        id_df = dup_df[id_cols].drop_duplicates()
        grouped_cols = [col for col in dup_df.columns if col not in id_cols]
        for col in grouped_cols:
            col_df = dup_df.loc[
                ~series_is_nan(dup_df[col]),
                id_cols + [col],
            ].drop_duplicates()
            col_df['dup_count'] = col_df.groupby(id_cols).transform('count')
            duplicate_rows = col_df['dup_count'] > 1
            if duplicate_rows.any():
                logger.info(
                    'On column %s setting %d values to null because of duplicates',
                    col,
                    duplicate_rows.sum(),
                )
            col_df[col] = col_df[col].mask(
                duplicate_rows,
                get_dtype_null(col_df[col].dtype)
            )
            col_df = col_df.drop_duplicates()
            id_df = id_df.merge(
                col_df[id_cols + [col]],
                validate='1:1',
                how='left',
                on=id_cols,
            )
        return id_df


input_table_dict = {}


def add_input_table(input_table: InputTable):

    def decorator():
        table_instance = input_table()
        input_table_dict[table_instance.name] = table_instance
        return input_table

    return decorator()


class NoMatchedTable(Exception):

    def __init__(self, message: str):
        super().__init__(message)


def match_soongo_employee_id(
    table_to_match: pd.DataFrame,
    organization_name: str,
) -> pd.DataFrame:
    """ Add the SoonGo employee id to the table to match.

    :param table_to_match: table to add the SoonGo employee_id to
    :param employee_table: employee_table
    """
    if CollaboratorsModel.soongo_collab_reference.name not in table_to_match.columns:
        table_to_match[CollaboratorsModel.soongo_collab_reference.name] = ''

    # First match based on customer employee id
    db_engine = gen_engine(database_url=os.environ['DATABASE_URL'])
    with db_engine.connect() as connection:
        collaborator_unique_column = connection.execute(
            sa.select(
                OrganizationParametersTable.value['value']
            ).select_from(
                OrganizationParametersTable
            ).join(
                OrganizationsTable,
                sa.and_(
                    OrganizationsTable.id == OrganizationParametersTable.organization_id,
                    OrganizationsTable.slug == organization_name,
                    OrganizationParametersTable.name == 'collaborator_unique_id',
                )
            )
        ).scalar()
        if (
            (collaborator_unique_column in table_to_match.columns)
            and
            (collaborator_unique_column != CollaboratorsModel.soongo_collab_reference.name)
        ):
            subset = pd.read_sql(
                sql=sa.select(
                    CollaboratorsTable.soongo_collab_reference,
                    getattr(CollaboratorsTable, collaborator_unique_column),
                ).select_from(
                    CollaboratorsTable
                ).join(
                    OrganizationsTable,
                    sa.and_(
                        OrganizationsTable.id == CollaboratorsTable.organization_id,
                        OrganizationsTable.slug == organization_name,
                    )
                ),
                con=connection,
            )
            subset = subset.loc[~series_is_nan(subset[collaborator_unique_column])]

            # In some organization the column which should be unique is sometimes duplicated
            # e.g. email for acorus. In this case we cannot match duplicates and match the others
            if subset[collaborator_unique_column].duplicated().any():
                subset = subset.loc[
                    ~subset[collaborator_unique_column].duplicated(keep=False),
                ]
            subset = subset.rename(
                columns={
                    CollaboratorsModel.soongo_collab_reference.name: 'employee_id_temp'
                },
            )
            table_to_match = table_to_match.merge(
                right=subset,
                on=collaborator_unique_column,
                how='left',
                validate='m:1',
            )
            table_to_match[CollaboratorsModel.soongo_collab_reference.name] = (
                table_to_match[CollaboratorsModel.soongo_collab_reference.name].mask(
                    ~series_is_nan(table_to_match['employee_id_temp']),
                    table_to_match['employee_id_temp']
                )
            )
            table_to_match.drop(columns='employee_id_temp', inplace=True)

    # Then match based on name - match alternative names to ids
    full_names = (
        table_to_match[CollaboratorsModel.employee_full_name.name]
        if CollaboratorsModel.employee_full_name.name in table_to_match.columns
        else None
    )
    first_names = (
        table_to_match[CollaboratorsModel.firstname.name]
        if CollaboratorsModel.firstname.name in table_to_match.columns
        else None
    )
    last_names = (
        table_to_match[CollaboratorsModel.lastname.name]
        if CollaboratorsModel.lastname.name in table_to_match.columns
        else None
    )
    table_to_match[CollaboratorsModel.soongo_collab_reference.name] = (
        table_to_match[CollaboratorsModel.soongo_collab_reference.name].mask(
            str_is_nan(table_to_match[CollaboratorsModel.soongo_collab_reference.name]),
            gen_soongo_emp_id(
                full_name_series=full_names,
                firstname_series=first_names,
                lastname_series=last_names,
                df_index=table_to_match.index,
                organization_name=organization_name,
            )
        )
    )
    assert CollaboratorsModel.soongo_collab_reference.name in table_to_match.columns

    return table_to_match


def get_collab_from_plate(
    table_to_match: pd.DataFrame,
    organization_name: str,
    date_col: str,
    logger: logging.Logger,
) -> pd.DataFrame:
    """ Add the SoonGo employee id to the table to match from a date and
    plate_number
    :param table_to_match: table to add the SoonGo employee_id to
    :param organization_name: name of the organization
    :param date_col: name of the date column
    :param logger: logger
    """
    if CollaboratorsModel.soongo_collab_reference.name not in table_to_match.columns:
        table_to_match[CollaboratorsModel.soongo_collab_reference.name] = ''

    if VehiclesModel.plate_number.name not in table_to_match.columns:
        raise ValueError(
            'Table to match does not contain plate_number column'
        )

    if date_col not in table_to_match.columns:
        raise ValueError(
            f'Table to match does not contain date column {date_col}'
        )
    initial_cols = list(table_to_match.columns)

    # First match based on customer employee id
    db_engine = gen_engine(database_url=os.environ['DATABASE_URL'])
    with db_engine.connect() as connection:
        plate_to_collab = pd.read_sql(
            sql=sa.select(
                VehiclesTable.plate_number,
                CollaboratorsTable.soongo_collab_reference.label('new_collab_ref'),
                VehicleAttributionsTable.date_from.label('association_date_from'),
                VehicleAttributionsTable.date_to.label('association_date_to'),
            ).select_from(
                VehicleAttributionsTable
            ).join(
                VehiclesTable,
                VehiclesTable.id == VehicleAttributionsTable.vehicle_id,
            ).join(
                OrganizationsTable,
                sa.and_(
                    OrganizationsTable.id == VehiclesTable.organization_id,
                    OrganizationsTable.slug == organization_name,
                )
            ).join(
                # inner join because specifically interested in adding collab
                CollaboratorsTable,
                CollaboratorsTable.id == VehicleAttributionsTable.collaborator_id,
            ),
            con=connection,
        )

    if not table_to_match.index.is_unique:
        logger.warning(
            'Table to match has non unique index, reindexing'
        )
        table_to_match = table_to_match.reset_index(drop=True)

    table_to_match.reset_index(
        inplace=True,
        names='original_index'
    )
    table_to_match = table_to_match.merge(
        how='left',
        right=plate_to_collab,
        on=VehiclesModel.plate_number.name,
        validate='m:m',
        indicator=False,
    )

    # Filter out duplicate rows
    table_to_match['is_within'] = table_to_match[date_col].dt.tz_localize(
        tz='Europe/Paris',
    ).between(
        table_to_match['association_date_from'],
        table_to_match['association_date_to'].fillna(
            pd.Timestamp('now', tz='UTC')
        ),
        inclusive='both',
    )
    table_to_match['row_within'] = table_to_match.groupby('original_index')[
        'is_within'
    ].transform('max')
    # Either not merged, or merged and the one row within range,
    # or not merged and no row within range
    table_to_match = table_to_match.loc[
        (table_to_match['is_within'] == 1)
        |
        # if no rows where merged then row_within will be 0
        (table_to_match['row_within'] == 0)
    ]
    table_to_match[CollaboratorsModel.soongo_collab_reference.name] = (
        table_to_match[CollaboratorsModel.soongo_collab_reference.name].mask(
            (table_to_match['is_within'] == 1) &
            str_is_nan(table_to_match[CollaboratorsModel.soongo_collab_reference.name]),
            table_to_match['new_collab_ref']
        )
    )
    table_to_match = table_to_match[
        initial_cols + ['original_index']
    ].drop_duplicates()

    assert table_to_match['original_index'].is_unique, (
        'Some original rows were duplicated after collaborator matching'
    )
    return table_to_match


def keep_duplicates(
    duplicated_df: pd.DataFrame,
    unique_cols: List[str],
    selection_col: str,
    logger: logging.Logger,
    selection_func: Union[Callable, str] = 'max',
) -> pd.DataFrame:
    """ Select duplicated values based on a selectin col and selection func

    :param duplicated_df: DataFrame to drop duplicates from
    :param unique_cols: list of column names to identify duplicates with
    :param selection_col: name of the column whose value to use to drop
        duplicates
    :param selection_func: callable to pass selection col to obtain values
        to keep

    :return: dataframe having dropped duplicated based on selection col and
        func
    """
    start_rows = len(duplicated_df)
    start_cols = set(duplicated_df[unique_cols])
    is_na_series = series_is_nan(duplicated_df[selection_col])

    selection_values = duplicated_df.groupby(
        unique_cols
    )[selection_col].transform(selection_func)
    duplicated_df = duplicated_df.loc[
        (duplicated_df[selection_col] == selection_values) | is_na_series,
    ]
    logger.info(
        'Dropped %d duplicated rows using %s; %d duplicates remaining',
        len(duplicated_df) - start_rows,
        selection_col,
        duplicated_df[unique_cols].duplicated().sum(),
    )
    if start_cols != set(duplicated_df[unique_cols]):
        raise ValueError(
            'Some cols were lost during deduplication process: '
            f'{start_cols.difference(duplicated_df)}',
        )
    return duplicated_df


def gen_soongo_emp_id(
    full_name_series: typing.Optional[pd.Series],
    firstname_series: typing.Optional[pd.Series],
    lastname_series: typing.Optional[pd.Series],
    df_index: pd.Index,
    organization_name: str,
) -> pd.Series:
    is_first_name = firstname_series is not None
    is_last_name = lastname_series is not None
    is_full_name = full_name_series is not None

    if is_first_name and is_last_name and is_full_name:
        soongo_collab_reference = (
            full_name_series.mask(
                str_is_nan(full_name_series),
                (
                    firstname_series +
                    ' ' +
                    lastname_series
                ),
            )
        )

    elif is_full_name:
        soongo_collab_reference = full_name_series

    elif is_first_name and is_last_name:
        soongo_collab_reference = (
            firstname_series +
            ' ' +
            lastname_series
        )

    else:
        soongo_collab_reference = pd.Series(
            '',
            dtype='string',
            index=df_index,
        )

    return NamesConverter(organization_name)(
        soongo_collab_reference
    )


def regroup_dataframe(
    raw_df: pd.DataFrame,
    groupby_col: str,
    logger: logging.Logger,
    ignore_cols: List[str] = [],
) -> pd.DataFrame:
    """ Regroup different rows of the DataFrame in a single row.

    :param raw_df: DataFrame to regroup
    :param groupby_col: column name to regroup on
    :param ignore_cols: columns to ignore when deduplicating
    """
    grouped_cols = [col for col in raw_df.columns if col != groupby_col]
    raw_df = raw_df.sort_values(groupby_col)

    # Forward fill within group
    raw_df[grouped_cols] = raw_df.groupby(groupby_col)[grouped_cols].ffill()

    # Backfil within group
    raw_df[grouped_cols] = raw_df.groupby(groupby_col)[grouped_cols].bfill()

    # Drop duplicates
    original_rows = len(raw_df)
    duplicated_entries = raw_df[groupby_col].duplicated().sum()

    new_df = raw_df.drop_duplicates(
        subset=[col for col in raw_df if col not in ignore_cols]
    )
    logger.info(
        'Regrouping using col %s resulting in dropping %d rows '
        'from %d duplicated entries',
        groupby_col,
        original_rows - len(new_df),
        duplicated_entries,
    )
    return new_df


def fetch_organization_params(organization_name: str) -> dict:
    """ Fetch organization params for input tables

    :param organization_name: name of the organization
    """
    with open(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'input_table_config.yaml',
        )
    ) as config_file:
        return yaml.safe_load(config_file)[organization_name]


def combine_connector_data(
    connector_data: ConnectorData,
    logger: logging.Logger,
    exclude_tables: Optional[Set[Tuple[str, str, str]]] = None,
    include_tables: Optional[Set[Tuple[str, str, str]]] = None,
    disjunctive_cols: Optional[List[Set[str]]] = None,
    conjunctive_cols: Optional[List[Set[str]]] = None,
):
    """ Collects all employee names, id, or other employee relevant columns
    across all connectors datasets.

    :param connector_data: an instanciated ConnectorData object
    :param logger: logger
    :param exclude_tables: Set of tables to exclude. Each table is
        identified by a tuple of string with its source connector, source
        dataset, and table name. If not specified, exclude None. If '*' is
        specified  asctable name, all tables from this source/dataset are
        excluded, if '*' is specified as dataset name, all datasets from that
        connector are excluded. exclude_tables supersedes include_tables -
        tables excluded in this arg will be excluded even if specified in
        include_tables.
    :param include_table: Set of tables to include. Each table is
        identified by a tuple of string with its source connector, source
        dataset, and table name. If not specified, include all. If '*' is
        specified  as table name, all tables from this source/dataset are
        included, if '*' is specified as dataset name, all datasets from that
        connector are included. exclude_tables supersedes include_tables -
        tables excluded in this arg will be excluded even if specified in
        include_tables.
    :param disjunctive_cols: List of sets of column names as string. For the
        dataset to be returned, at least one column must be available in each
        set.
    :param conjunctive_cols: List of sets of column names as string. These
        columns are not necessary to return the dataset, but all columns in
        the set must be available for them to be added to the dataset.

    :raises NoMatchedTable: if no Table is matched

    :return: a pandas DataFrame
    """
    MAX_INCLUDE_TABLES_VARIABLE = 4
    df_lst = []
    exclude_tables = (
        {tuple(table_list) for table_list in exclude_tables}
        if exclude_tables else set()
    )
    include_tables = (
        {tuple(table_list) for table_list in include_tables}
        if include_tables else set()
    )

    if not include_tables:
        for source in connector_data:
            for element in source:
                if isinstance(element, pd.DataFrame):
                    if element.empty:
                        continue
                    if get_sources_from_df(element) in exclude_tables:
                        continue
                    subset_df = subset_cols(
                        df=element,
                        disjunctive_cols=disjunctive_cols,
                        conjunctive_cols=conjunctive_cols,
                    )
                    if subset_df is not None:
                        df_lst.append(subset_df)

                else:
                    assert isinstance(element, Dataset)
                    for df in element:
                        assert isinstance(df, pd.DataFrame)
                        if df.empty:
                            continue
                        if get_sources_from_df(df) in exclude_tables:
                            continue
                        subset_df = subset_cols(
                            df=df,
                            disjunctive_cols=disjunctive_cols,
                            conjunctive_cols=conjunctive_cols,
                        )
                        if subset_df is not None:
                            df_lst.append(subset_df)

    else:
        for table_tup in include_tables:
            if table_tup in exclude_tables:
                continue
            variables = [None] * MAX_INCLUDE_TABLES_VARIABLE
            variables = map(itemgetter(0), zip_longest(table_tup, variables))
            connector, dataset, table, filepath = variables
            if filepath:
                element = connector_data.get(
                    connector_name=connector,
                    dataset_name=dataset,
                ).get(
                    data_source_name=table,
                    data_path=[filepath],
                )
            else:
                element = connector_data.get(
                    connector_name=connector,
                    dataset_name=dataset if dataset != '*' else None,
                    table_name=table if table != '*' else None,
                )
            if isinstance(element, pd.DataFrame):
                subset_df = subset_cols(
                    df=element,
                    disjunctive_cols=disjunctive_cols,
                    conjunctive_cols=conjunctive_cols,
                )
                if subset_df is not None:
                    df_lst.append(subset_df)
            elif isinstance(element, Dataset):
                for df in element:
                    assert isinstance(df, pd.DataFrame)
                    subset_df = subset_cols(
                        df=df,
                        disjunctive_cols=disjunctive_cols,
                        conjunctive_cols=conjunctive_cols,
                    )
                    if subset_df is not None:
                        df_lst.append(subset_df)
            else:
                for dataset in element:
                    assert isinstance(dataset, Dataset)
                    for df in dataset:
                        assert isinstance(df, pd.DataFrame)
                        subset_df = subset_cols(
                            df=df,
                            disjunctive_cols=disjunctive_cols,
                            conjunctive_cols=conjunctive_cols,
                        )
                        if subset_df is not None:
                            df_lst.append(subset_df)

    if df_lst == []:
        raise NoMatchedTable(
            'No dataframe contained any columns of interest across all'
            'connectors.'
        )

    combined_df = pd.concat(df_lst, axis=0, ignore_index=True)
    logger.info(
        'Collected %d entries from %d datasets',
        len(combined_df),
        len(df_lst),
    )
    return combined_df


def subset_cols(
    df: pd.DataFrame,
    disjunctive_cols: Optional[List[Set[str]]] = None,
    conjunctive_cols: Optional[List[Set[str]]] = None,
) -> Optional[pd.DataFrame]:
    """ Subset df to return dataframe with columns of interest if any

    :param df: pandas Dataframe possibly containing employees information
    :param disjunctive_cols: List of sets of column names as string. For the
    dataset to be returned, at least one column must be available in each set.
    :param conjunctive_cols: List of sets of column names as string. These
    columns are not necessary to return the dataset, but all columns in the set
    must be available for them to be added to the dataset.

    :return: dataframe with employee relevant cols, or None if None
    """
    # Handle args. If no column criterion specified then then take all
    if disjunctive_cols is None and conjunctive_cols is None:
        conjunctive_cols = [
            {col} for col in df.columns
        ]
        disjunctive_cols = []
    elif disjunctive_cols is None:
        disjunctive_cols = []  # Cannot set [] by default because it is mutable
    elif conjunctive_cols is None:
        conjunctive_cols = []
    required_cols = set()

    # Handle disjunctive cols - return None if at least one col available in
    # each disjunctive set.
    for disjunctive_set in disjunctive_cols:
        col_set = set(disjunctive_set).intersection(df.columns)
        if not col_set:
            return
        required_cols = required_cols.union(disjunctive_set)

    # Handle conjunctive cols - adds them if all col in the set available
    cols_to_add = set()
    for conjunctive_set in conjunctive_cols:
        if set(conjunctive_set).issubset(df.columns):
            cols_to_add = cols_to_add.union(conjunctive_set)
    cols_to_add = required_cols.union(cols_to_add)

    if cols_to_add:  # If not (no disjunctive cols and no match in conjunctive)
        return df[list(cols_to_add.intersection(df.columns))]


def get_sources_from_df(df: pd.DataFrame) -> Tuple[str, str, str]:
    """ Return the source connector, dataset, and table of a dataframe."""
    if not {
        SoonGoRecordsModel.connector_name.name,
        SoonGoRecordsModel.source_dataset.name,
        SoonGoRecordsModel.source_dataset.name,
    }.issubset(df.columns):
        raise ValueError(
            f'The df does not have the required source columns to evaluate'
            f'its sources: {df.columns}'
        )

    connector_name = df[SoonGoRecordsModel.connector_name.name].unique()
    if len(connector_name) != 1:
        raise ValueError(
            f'No single connector_name value: {connector_name}'
        )
    connector_name = connector_name[0]

    source_dataset = df[SoonGoRecordsModel.source_dataset.name].unique()
    if len(source_dataset) != 1:
        raise ValueError(
            f'No single source_dataset value: {source_dataset}'
        )
    source_dataset = source_dataset[0]

    source_table = df[SoonGoRecordsModel.source_table.name].unique()
    if len(source_table) != 1:
        raise ValueError(
            f'No single source_table value: {source_table}'
        )
    source_table = source_table[0]

    return connector_name, source_dataset, source_table


def add_synchronization_id(
    df: pd.DataFrame,
    connector_data: ConnectorData,
) -> pd.DataFrame:
    """ Add the synchronization id and type using the synchronisation_id_dict
    property of ConnectorData. Synchronization_type is by default csv_upload

    :param df: df to add synchronization id and type to
    :param connector_data: connector_data the df was generated from
    :param synchronization_type: type of the synchronisation, by default CSV_UPLOAD

    :raises ValueError: if the df does not contain a column connector_name

    :returns: df with two added columns
    """
    if SoonGoRecordsModel.connector_name.name not in df.columns:
        raise ValueError(
            'A connector_name column is necessary to map synchronization_id'
        )

    missing_connectors = set(
        df[SoonGoRecordsModel.connector_name.name].unique()
    ).difference(
        connector_data.synchronisation_id_dict.keys()
    )
    if missing_connectors:
        raise ValueError(
            f'Provided connector dict keys {connector_data.synchronisation_id_dict.keys()}'
            f'do not cover the following connector_names: {missing_connectors}'
        )

    df[SoonGoRecordsModel.synchronisation_id.name] = (
        df[SoonGoRecordsModel.connector_name.name].map(
            connector_data.synchronisation_id_dict,
        )
    )
    assert not str_is_nan(df[SoonGoRecordsModel.synchronisation_id.name]).any()

    return df


def check_no_future_dates(
    date_tol: pd.Timestamp,
    data_df: pd.DataFrame,
    date_var: str,
    table_name: str,
    logger: logging.Logger,
    raise_error: bool = True,
) -> None:
    """ Check for future dates in the data
    :param date_tol: date at which to start raising issues
    :param data_df: DataFrame to check
    :param table_name: name of the table to check
    :param logger: logger
    :param raise_error: whether to raise an error or just log it
    """
    future_dates = (
        data_df[date_var] > date_tol
    )
    if future_dates.any():
        connectors_at_stake = data_df.loc[
            future_dates,
            'connector_name',
        ].unique().tolist()
        if raise_error:
            raise ValueError(
                f'Future dates found in {table_name} table for connectors: '
                f'{connectors_at_stake}'
            )
        else:
            logger.error(
                f'Future dates found in {table_name} table for connectors: '
                f'{connectors_at_stake}'
            )
