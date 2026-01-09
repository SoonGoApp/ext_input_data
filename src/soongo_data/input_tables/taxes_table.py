""" Script to calculate the taxes table to load in database."""
import logging
import os
import typing

import pandas as pd

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (BusinessUnitsModel, CollaboratorsModel,
                                     SoonGoRecordsModel, TaxesModel,
                                     VehiclesModel)
from soongo_data.input_tables.employees_table import EmployeesInputTable
from soongo_data.input_tables.vehicles_table import VehiclesInputTable
from soongo_data.sql_mappings import TaxesTable
from soongo_data.utils.bu import get_business_units
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id,
                                            match_soongo_employee_id)
from soongo_data.utils.logging_utils import gen_logger


@add_input_table
class TaxesInputTable(InputTable):
    def __init__(self):
        super().__init__(
            sql_mapping=TaxesTable,
            date_col_name='billing_date',
            columns=[
                InputColumn.from_data_column(
                    column=CollaboratorsModel.soongo_collab_reference,
                    foreign_relationship=(
                        EmployeesInputTable().name,
                        CollaboratorsModel.soongo_collab_reference.name,
                    ),
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=BusinessUnitsModel.business_unit,
                    format=r'\w+(?: > \w+)*',
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.plate_number,
                    foreign_relationship=(
                        VehiclesInputTable().name,
                        VehiclesModel.plate_number.name,
                    ),
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=TaxesModel.billing_date,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=TaxesModel.declared_non_deductible_amortization,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=TaxesModel.tax_vehicle_age,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=TaxesModel.tax_corporate_vehicles,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=TaxesModel.tax_CO2_emission,
                    is_id=True,
                    sql_name='tax_co2_emission',
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
                    column=TaxesModel.tax_pollutant,
                    is_id=True,
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
        tax_cols = self.return_column_names()
        # Get tax data
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

        combined_df[TaxesModel.billing_date.name] = self.gen_billing_date(
            combined_df
        )

        # Some rows have no taxes (year was specified but no info)
        combined_df = self.fill_missing_cols(
            df=combined_df,
        )
        combined_df = combined_df.loc[
            pd.notna(combined_df[[
                TaxesModel.declared_non_deductible_amortization.name,
                TaxesModel.tax_vehicle_age.name,
                TaxesModel.tax_corporate_vehicles.name,
                TaxesModel.tax_CO2_emission.name,
            ]]).any(axis=1)
        ]
        return combined_df[tax_cols]

    @staticmethod
    def gen_billing_date(tax_df: pd.DataFrame) -> pd.Series:
        """ Returns the last day of the year for the years in Series."""
        if TaxesModel.billing_date.name not in tax_df.columns:
            tax_df[TaxesModel.billing_date.name] = pd.NaT

        if TaxesModel.ikb_start_date.name in tax_df.columns:
            tax_df[TaxesModel.billing_date.name] = (
                tax_df[TaxesModel.billing_date.name].fillna(
                    tax_df[TaxesModel.ikb_start_date.name]
                )
            )
            assert pd.notna(
                tax_df.loc[
                    pd.notna(tax_df[TaxesModel.ikb_start_date.name]),
                    TaxesModel.billing_date.name
                ]
            ).all()

        if TaxesModel.quarter.name in tax_df.columns:
            assert TaxesModel.year.name in tax_df.columns
            quarter_dict = {
                'Trimestre 1': '01',
                'Trimestre 2': '04',
                'Trimestre 3': '07',
                'Trimestre 4': '10',
            }
            tax_df[TaxesModel.billing_date.name] = (
                tax_df[TaxesModel.billing_date.name].fillna(
                    pd.to_datetime(
                        (
                            tax_df[TaxesModel.year.name].fillna('').astype(str)
                            + '-' +
                            tax_df[TaxesModel.quarter.name].map(quarter_dict) +
                            '-01'
                        ),
                        format=r'%Y-%m-%d',
                    ),
                )
            )
            assert pd.notna(
                tax_df.loc[
                    pd.notna(tax_df[TaxesModel.quarter.name]) &
                    pd.notna(tax_df[TaxesModel.year.name]),
                    TaxesModel.billing_date.name
                ]
            ).all()

        if TaxesModel.year.name in tax_df.columns:
            tax_df[TaxesModel.billing_date.name] = (
                tax_df[TaxesModel.billing_date.name].fillna(
                    pd.to_datetime(
                        tax_df[TaxesModel.year.name].astype(str) + '-12-31',
                        format=r'%Y-%m-%d',
                    ),
                )
            )
            assert pd.notna(
                tax_df.loc[
                    pd.notna(tax_df[TaxesModel.year.name]),
                    TaxesModel.billing_date.name
                ]
            ).all()

        return tax_df[TaxesModel.billing_date.name]


if __name__ == "__main__":
    logger = gen_logger('taxes_table')
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
    taxes_table = TaxesInputTable()
    taxes_df = taxes_table.get(
        connector_data=connector_data,
        logger=logger,
    )
    taxes_table.check_columns(
        data_df=taxes_df,
        collaborators=EmployeesInputTable().get(
            connector_data=connector_data,
            logger=logger,
        ),
        vehicles=VehiclesInputTable().get(
            connector_data=connector_data,
            logger=logger,
        ),
        logger=logger,
    )
    taxes_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{taxes_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
