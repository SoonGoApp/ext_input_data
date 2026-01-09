"""
Script and logic to upload an input table information to db
"""
import argparse
import logging
import os
import typing
from datetime import datetime

import pandas as pd
import yaml
from sqlalchemy.ext.declarative import DeclarativeMeta

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import CollaboratorsModel, VehiclesModel
from soongo_data.input_tables.accident_table import AccidentsInputTable  # NOQA
from soongo_data.input_tables.controls_table import ControlsInputTable  # NOQA
from soongo_data.input_tables.business_unit_connector_ids import \
    BusinessUnitConnectorIdsInputTable  # NOQA
from soongo_data.input_tables.collaborator_connector_ids import \
    CollaboratorConnectorIdsInputTable  # NOQA
from soongo_data.input_tables.employees_table import EmployeesInputTable
from soongo_data.input_tables.equipment_categories_assignment_table import \
    EquipmentCategoriesAssignmentInputTable  # NOQA
from soongo_data.input_tables.equipment_table import \
    EquipmentsInputTable  # NOQA
from soongo_data.input_tables.expense_claims import \
    ExpenseClaimsInputTable  # NOQA
from soongo_data.input_tables.expense_table import ExpensesInputTable  # NOQA
from soongo_data.input_tables.hotels_table import HotelsInputTable  # NOQA
from soongo_data.input_tables.in_kind_table import InKindBenefitsInputTable  # NOQA
from soongo_data.input_tables.mileage_table import MileagesInputTable  # NOQA
from soongo_data.input_tables.rental_cars import RentalCarsInputTable  # NOQA
from soongo_data.input_tables.service_table import ServicesInputTable  # NOQA
from soongo_data.input_tables.taxes_table import TaxesInputTable  # NOQA
from soongo_data.input_tables.train_plane import TravelInputTable  # NOQA
from soongo_data.input_tables.vehicle_eco_score import VehicleEcoScoreInputTable # NOQA
from soongo_data.input_tables.vehicle_associations import \
    VehicleAssociationsInputTable  # NOQA
from soongo_data.input_tables.vehicle_connector_ids import \
    VehicleConnectorIdsInputTable  # NOQA
from soongo_data.input_tables.vehicle_contracts import \
    VehicleContractsInputTable  # NOQA
from soongo_data.input_tables.vehicle_status_history import \
    VehiclesStatusInputTable  # NOQA
from soongo_data.input_tables.vehicles_table import VehiclesInputTable  # NOQA
from soongo_data.input_tables.documents_upload import DocumentsUploadInputTable  # NOQA
from soongo_data.utils.db import get_organization_id, session_scope
from soongo_data.utils.input_tables import InputTable, input_table_dict
from soongo_data.utils.logging_utils import gen_logger


def main(
    input_table: InputTable,
    connector_data: ConnectorData,
    logger: logging.Logger,
    update_values: str,
    database_url: str,
    min_date: typing.Optional[typing.Dict[str, pd.Timestamp]] = None,
    max_date: typing.Optional[typing.Dict[str, pd.Timestamp]] = None,
    columns: typing.Optional[typing.List[str]] = None,
    fetch_params_dict: typing.Optional[dict] = None,
) -> None:
    """ Runs the insertion operation. First fetch the connector data,
    then filters the row already in database, lastly inserts the remainder.

    :param input_table: InputTable being inserted into db
    :param connector_data: ConnectorData object collecting all connector
        datasets for this organization
    :param table_func: function collecting the table data from the ConnectorData
    :param logger: logger
    :param update_values: whether to update existing values
    :param fetch_params_dict: optional params to override the
        input_table_config
    """
    organization_id = get_organization_id(
        organization_name=connector_data.organization_name,
        database_url=database_url
    )
    data_df = input_table.get(
        connector_data=connector_data,
        logger=logger,
        fetch_params_dict=fetch_params_dict,
    )
    logger.info(
        'Fetched %d rows from connectors for table %s',
        len(data_df),
        input_table.name,
    )
    if min_date:
        for date_col, min_date_value in min_date.items():
            if date_col not in data_df.columns:
                raise ValueError(
                    f'The column {date_col} in the min_date dict does not exist in the fetched data'
                )
            original_rows = len(data_df)
            min_date_value = datetime.fromordinal(pd.Timestamp(min_date_value).toordinal())
            data_df = data_df[data_df[date_col] >= min_date_value]
            logger.warning(
                'Dropped %d rows from table %s because %s was before the min date %s',
                original_rows - len(data_df),
                input_table.name,
                date_col,
                min_date_value,
            )

    if max_date:
        for date_col, max_date_value in max_date.items():
            if date_col not in data_df.columns:
                raise ValueError(
                    f'The column {date_col} in the max_date dict does not exist in the fetched data'
                )
            original_rows = len(data_df)
            max_date_value = datetime.fromordinal(pd.Timestamp(max_date_value).toordinal())
            data_df = data_df[data_df[date_col] < max_date_value]
            logger.warning(
                'Dropped %d rows from table %s because %s was on or after the max date %s',
                original_rows - len(data_df),
                input_table.name,
                date_col,
                max_date_value,
            )

    if not data_df.empty:
        with session_scope(database_url=database_url) as session:
            input_table.to_sql(
                data_df=data_df,
                organization_id=organization_id,
                session=session,
                logger=logger,
                update_values=update_values,
                columns=columns,
            )


def parse_args() -> argparse.Namespace:
    """ Parse execution params

    :returns: execution params as attributes of a namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-o',
        '--org-name',
        type=str,
        help='The name of the organization',
    )
    parser.add_argument(
        '-t',
        '--table-names',
        type=str,
        nargs='+',
        help='List of table names',
        default=['*'],
    )
    parser.add_argument(
        '-f',
        '--folder',
        type=str,
        help='Path to the data folder storing all organization data',
        default='/home/matthieuglotz/Documents/Data/soongo-local',
    )
    parser.add_argument(
        '-p',
        '--fetch-params-dict',
        type=yaml.safe_load,
        help='Fetch param dict. Optional, if not provided defaults to config.',
        default='{}',
        required=False,
    )
    parser.add_argument(
        '-u',
        '--update-values',
        type=str,
        default='null_only',
        help=(
            'Whether to overwrite existing values. null_only to fill in '
            'missing values, overwrite to replace existing values, keep to '
            'not update any existing values, inc_null to overwrite existing '
            'even if new value is null'
        ),
    )
    parser.add_argument(
        '-min',
        '--min_date',
        type=yaml.safe_load,
        default=None,
        help=(
            'Dict of date column name to minimum date.'
        ),
    )
    parser.add_argument(
        '-max',
        '--max_date',
        type=yaml.safe_load,
        default=None,
        help=(
            'Dict of date column name to maximum date.'
        ),
    )
    parser.add_argument(
        '-c',
        '--columns',
        type=str,
        nargs='+',
        default=None,
        help=(
            'A list of column names to update. If not within the columns, no update'
        ),
    )
    parser.add_argument(
        '--db-url',
        type=str,
        required=True,
        help='Database url',
    )

    args = parser.parse_args()

    if not (
        set(args.table_names).issubset(input_table_dict.keys())
        or '*' in args.table_names
    ):
        raise ValueError(
            f'The only accepted values for table_names are * or '
            f'{input_table_dict.keys()}'
        )

    if not os.path.isdir(args.folder):
        raise FileNotFoundError(
            f'The passed folder {args.folder} does not exists',
        )

    return args


def get_id_cols(input_table: InputTable) -> typing.List[str]:
    """ Get id column names, i.e. the name of the columns which will be used
    to uniquely identify entries on this table

    :param input_table: InputTable to insert data from

    :returns: list of column names to be used as ids
    """
    conversion_dict = {}
    if input_table.name != EmployeesInputTable().name:
        conversion_dict = {
            CollaboratorsModel.soongo_collab_reference.name: 'collaborator_id',
        }
    if input_table.name != VehiclesInputTable().name:
        conversion_dict.update(
            {VehiclesModel.plate_number.name: VehiclesModel.vehicle_id.name}
        )
    return [
        conversion_dict.get(col.name, col.name)
        for col in input_table.columns if col.is_id
    ]


def get_mapping_col_names(sql_mapping: DeclarativeMeta) -> typing.List[str]:
    """ Get the str column name of the sql_mapping

    :param sql_mapping: SQLAlchemy declarative table mapping

    :returns: list of mapping column names
    """
    return [col.name for col in sql_mapping.__table__.columns]


if __name__ == '__main__':
    args = parse_args()
    logger = gen_logger('insert to db')
    logger.info(
        'Starting to collect connector data for organization %s',
        args.org_name,
    )

    os.environ['DATABASE_URL'] = args.db_url

    connector_data = ConnectorData(
        root_folder=args.folder,
        organization_name=args.org_name,
    )

    tables_to_fetch = input_table_dict.keys() if '*' in args.table_names else args.table_names
    for table in tables_to_fetch:
        input_table = input_table_dict[table]
        logger.info(
            'Starting data fetch and insert process for table %s',
            input_table.name,
        )
        main(
            input_table=input_table,
            connector_data=connector_data,
            logger=logger,
            update_values=args.update_values,
            database_url=args.db_url,
            fetch_params_dict=args.fetch_params_dict,
            min_date=args.min_date,
            max_date=args.max_date,
            columns=args.columns,
        )
