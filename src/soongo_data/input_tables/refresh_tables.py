""" Refresh tables

Refresh tables for a given client - given a path.
"""
import argparse
import os

from soongo_data.connectors import ConnectorData
from soongo_data.input_tables.accident_table import AccidentsInputTable
from soongo_data.input_tables.employees_table import EmployeesInputTable
from soongo_data.input_tables.expense_claims import ExpenseClaimsInputTable
from soongo_data.input_tables.expense_table import ExpensesInputTable
from soongo_data.input_tables.hotels_table import HotelsInputTable
from soongo_data.input_tables.mileage_table import MileagesInputTable
from soongo_data.input_tables.rental_cars import RentalCarsInputTable
from soongo_data.input_tables.taxes_table import TaxesInputTable
from soongo_data.input_tables.train_plane import TravelInputTable
from soongo_data.input_tables.vehicle_associations import \
    VehicleAssociationsInputTable
from soongo_data.input_tables.vehicle_contracts import \
    VehicleContractsInputTable
from soongo_data.input_tables.vehicles_table import VehiclesInputTable
from soongo_data.utils.logging_utils import gen_logger


def parse_args() -> argparse.Namespace:
    """ Argument parser for the script execution

    :returns: namespace containing the organization and folder arguments
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f', '--folder', type=str, required=False,
        default='/home/matthieuglotz/Documents/Data/soongo-local'
    )
    parser.add_argument(
        '-o', '--organization', type=str, required=True
    )
    _args = parser.parse_args()
    organisation_folder = os.path.join(
        os.path.expanduser(_args.folder),
        _args.organization,
    )
    if not os.path.isdir(organisation_folder):
        raise FileNotFoundError(
            f'The passed organisation / folder combo {organisation_folder} '
            'does not exist'
        )

    return _args


if __name__ == '__main__':
    logger = gen_logger('refresh_tables')
    args = parse_args()
    connector_data = ConnectorData(
        root_folder=args.folder,
        organization_name=args.organization,
    )
    employee_table = EmployeesInputTable().get(
        connector_data=connector_data,
        logger=logger,
    )
    vehicle_table = VehiclesInputTable().get(
        connector_data=connector_data,
        logger=logger,
    )
    for input_table in (
        AccidentsInputTable(),
        EmployeesInputTable(),
        ExpenseClaimsInputTable(),
        ExpensesInputTable(),
        HotelsInputTable(),
        MileagesInputTable(),
        RentalCarsInputTable(),
        TaxesInputTable(),
        TravelInputTable(),
        VehicleAssociationsInputTable(),
        VehiclesInputTable(),
        VehicleContractsInputTable(),
    ):
        logger.info(
            'Fetching information for table %s',
            input_table.name,
        )
        table_df = input_table.get(
            connector_data=connector_data,
            logger=logger
        )
        input_table.check_columns(
            data_df=table_df,
            logger=logger,
            collaborators=employee_table,
            vehicles=vehicle_table,
        )
        table_path = os.path.join(
            args.folder,
            args.organization,
            'webapp_tables',
            input_table.name + '_table.csv',
        )
        logger.info(
            'Saving table %s on path %s',
            input_table.name,
            table_path,
        )
        table_df.to_csv(
            table_path,
            index=False,
            sep=';',
        )
