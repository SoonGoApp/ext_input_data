""" Check tables content cross tables and organizations"""

import argparse
import dataclasses
import logging
import operator
import os
import typing

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process, utils

from soongo_data.data_models import (ClaimsModel, CollaboratorsModel,
                                     ExpensesModel, MileageReportsModel,
                                     TaxesModel, VehicleAssociationsModel,
                                     VehicleContractsModel, VehiclesModel)
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
from soongo_data.input_tables.vehicles_table import VehiclesInputTable
from soongo_data.utils.enums import (ContractType, CostCategory, ExpenseType,
                                     FuelTypes)
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.type import convert_string, df_is_nan, series_is_nan

TABLE_LST = [
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
]


@dataclasses.dataclass
class InputTables:

    def __init__(self: typing.Self, folder_path: str) -> typing.Self:
        self.folder_path = folder_path

        for table in TABLE_LST:
            setattr(
                self,
                table.name,
                pd.read_csv(
                    os.path.join(
                        folder_path,
                        table.name + '_table.csv',
                    ),
                    sep=';',
                    index_col=False,
                )
            )

    def get(self: typing.Self, table_name: str):
        return getattr(self, table_name)

    def __iter__(self):
        for table in TABLE_LST:
            yield table.name, self.get(table.name)


class TableChecks:

    RECURRING_COSTS = (
        CostCategory.rent_assistance.value,
        CostCategory.rent_financial_loss.value,
        CostCategory.rent_fuel_card.value,
        CostCategory.financial_rent.value,
        CostCategory.rent_maintenance.value,
        CostCategory.rent_management_fees.value,
        CostCategory.rent_replacement_vehicle_flat_fee.value,
        CostCategory.rent_telematic.value,
        CostCategory.rent_tires.value,
        CostCategory.insurance_assistance.value,
        CostCategory.insurance_financial_loss.value,
        CostCategory.insurance_glass.value,
        CostCategory.insurance_replacement_vehicle.value,
        CostCategory.insurance_vehicle.value,
    )

    MAGNITUDE_CHECKS = {
        VehicleContractsModel.lease_mileage.name: (0, 10**6),
        VehiclesModel.vehicle_age.name: (0, 12*25),
        VehiclesModel.fiscal_power.name: (0, 40),
        VehiclesModel.co2_per_km.name: (0, 0.3),
        VehiclesModel.theoretical_fuel_consumption.name: (0, 10),
        VehiclesModel.vehicle_max_rolling_weight.name: (0, 10000),
        MileageReportsModel.mileage.name: (0, 10**6),
        VehiclesModel.co2_production.name: (5**3, 20**4),
        VehiclesModel.co2_recycling.name: (-2**3, 0),
    }

    DATE_COHERENCE_CHECKS = {
        VehicleContractsModel.lease_start_date.name: operator.lt,
        VehiclesModel.entry_into_service_date.name: operator.lt,
        VehicleAssociationsModel.association_start_date.name: operator.lt,
        VehicleContractsModel.lease_end_date.name: operator.gt,
        VehicleAssociationsModel.association_end_date.name: operator.gt,
    }

    EXPENSE_METRICS = {
        'total_insurance_costs': (
            CostCategory.insurance_assistance.value,
            CostCategory.insurance_brokerage_cost.value,
            CostCategory.insurance_deductible_cost.value,
            CostCategory.insurance_financial_loss.value,
            CostCategory.insurance_glass.value,
            CostCategory.insurance_replacement_vehicle.value,
            CostCategory.insurance_vehicle.value,
            CostCategory.self_insurance.value,
        ),
        'total_other_costs': (
            CostCategory.real_replacement_vehicle_cost.value,
            CostCategory.real_short_term_rental.value,
            CostCategory.real_relay_vehicle_cost.value,
            CostCategory.real_medium_term_rental.value,
            CostCategory.rent_end_of_year.value,
            CostCategory.real_maintenance.value,
            CostCategory.real_telematics_fee.value,
            CostCategory.real_telematics_install.value,
            CostCategory.real_tires_summer.value,
            CostCategory.real_tires_winter.value,
            CostCategory.real_tires_other.value,
            CostCategory.real_glass.value,
            CostCategory.real_assistance.value,
            CostCategory.real_restitution.value,
            CostCategory.real_others.value,
            CostCategory.tolls_card.value,
            CostCategory.tolls_real.value,
            CostCategory.parking_card.value,
            CostCategory.parking_real.value,
            CostCategory.washing_card.value,
            CostCategory.washing_real.value,
            CostCategory.logo.value,
            CostCategory.real_repairs.value,
            CostCategory.charging_point_installation.value,
            CostCategory.charging_points_recurring.value,
        ),
        'total_energy': tuple(
            [fuel_type.value for fuel_type in FuelTypes]
        ),
        'total_rent': (
            CostCategory.financial_rent.value,
            CostCategory.rent_management_fees.value,
            CostCategory.rent_telematic.value,
            CostCategory.rent_tires.value,
            CostCategory.rent_financial_loss.value,
            CostCategory.rent_fuel_card.value,
            CostCategory.rent_replacement_vehicle_flat_fee.value,
            CostCategory.rent_replacement_vehicle_actual.value,
            CostCategory.rent_assistance.value,
            CostCategory.rent_others.value,
            CostCategory.real_medium_term_rental.value,
            CostCategory.rent_end_of_year.value,
            CostCategory.rent_maintenance.value,
        ),
        'ikb_no_fuel_expense_based': (
            CostCategory.financial_rent.value,
            CostCategory.rent_maintenance.value,
            CostCategory.rent_tires.value,
            CostCategory.rent_financial_loss.value,
            CostCategory.rent_end_of_year.value,
            CostCategory.insurance_vehicle.value,
            CostCategory.rent_financial_loss.value,
            CostCategory.insurance_financial_loss.value,
        ),
        'taxes_expense': (
            CostCategory.fines.value,
            CostCategory.environmental_bonus.value,
            CostCategory.environmental_malus.value,
        )
    }

    FLEET_CLAIMS = (
        ExpenseType.fuel.value,
        ExpenseType.maintenance.value,
        ExpenseType.parking.value,
        ExpenseType.repairs.value,
        ExpenseType.tolls.value,
    )

    def __init__(
        self,
        input_tables: InputTables,
        logger: logging.Logger,
        output_folder: str,
    ):
        self.input_tables = input_tables
        self.logger = logger
        self.output_folder = output_folder

    def run_checks(
        self: typing.Self,
        years: typing.Tuple[int] = (2021, 2022, 2023),
    ) -> None:
        """ Run availability and consistency checks across all tables and saves
        summary reports on output_folder.

        :returns: None but saves summary reports on output_folder
        """
        # Column level checks
        column_df = self.availability()
        column_df = column_df.merge(
            right=self.magnitude(),
            on=['table_name', 'column_name'],
            how='outer',
            validate='1:1',
        )
        column_df.to_csv(
            os.path.join(
                self.output_folder,
                'column_check.csv',
            ),
            index=False,
        )

        # Plate number level checks
        vehicle_df = self.recurrency()
        vehicle_df = vehicle_df.merge(
            right=self.date_consistency(),
            on=VehiclesModel.plate_number.name,
            how='outer',
            validate='1:1',
        )
        for year in years:
            vehicle_df = vehicle_df.merge(
                right=self.tco(year),
                on=VehiclesModel.plate_number.name,
                how='outer',
                validate='1:1',
            )

        vehicle_df.to_csv(
            os.path.join(
                self.output_folder,
                'vehicle_check.csv',
            ),
            index=False,
        )

        # Collaborator check
        collaborator_df = self.collaborators()
        collaborator_df.to_csv(
            os.path.join(
                self.output_folder,
                'collaborator_check.csv',
            ),
            index=False,
        )

    def availability(self: typing.Self) -> pd.DataFrame:
        """ Check number of missing columns in each table column

        :returns: None but saves share of missing values in each table columns
        """
        availability_df_lst = []
        for table_name, table_df in self.input_tables:
            nb_rows = len(table_df)
            nan_count = df_is_nan(table_df).sum(axis=0)
            nan_count = nan_count / nb_rows
            nan_count = nan_count.T.reset_index()
            nan_count = nan_count.rename(
                columns={0: "share_missing", "index": "column_name"}
            )
            nan_count['table_name'] = table_name
            availability_df_lst.append(nan_count)

        availability_df = pd.concat(availability_df_lst)
        return availability_df

    def recurrency(self: typing.Self) -> pd.DataFrame:
        """ Check whether expenses supposed to repeat repeated overtime

        :returns: None but logs share of missing repetitions in each column
        """
        expenses_df = self.input_tables.get(ExpensesInputTable().name).copy()
        vehicles_df = self.input_tables.get(VehiclesInputTable().name)
        expenses_df = expenses_df.merge(
            right=vehicles_df[
                [
                    VehiclesModel.plate_number.name,
                    VehicleContractsModel.contract_type.name,
                ]
            ],
            on=VehiclesModel.plate_number.name,
            how='left',
            indicator=True,
            validate='m:1',
        )
        assert (
            expenses_df.loc[
                ~series_is_nan(expenses_df[VehiclesModel.plate_number.name]),
                "_merge",
            ] == 'both'
        ).all()
        expenses_df = expenses_df.drop(columns='_merge')
        expenses_df[ExpensesModel.billing_date.name] = str_series_to_datetime(
            expenses_df[ExpensesModel.billing_date.name]
        )
        expenses_df = expenses_df.loc[
            expenses_df[ExpensesModel.soongo_category.name].isin(
                self.RECURRING_COSTS
            )
            & (expenses_df[ExpensesModel.net_amount.name] > 0),
            [
                VehiclesModel.plate_number.name,
                ExpensesModel.billing_date.name,
                ExpensesModel.soongo_category.name,
                VehicleContractsModel.contract_type.name,
            ]
        ]
        expenses_df['min_date'] = expenses_df.groupby(
            [
                VehiclesModel.plate_number.name,
                ExpensesModel.soongo_category.name,
            ]
        )[ExpensesModel.billing_date.name].transform('min')
        expenses_df['max_date'] = expenses_df.groupby(
            [
                VehiclesModel.plate_number.name,
                ExpensesModel.soongo_category.name,
            ]
        )[ExpensesModel.billing_date.name].transform('max')
        expenses_df['nb_months'] = (
            expenses_df['max_date'].dt.to_period('M').astype(int) -
            expenses_df['min_date'].dt.to_period('M').astype(int)
        )
        expenses_df['count'] = expenses_df.groupby(
            [
                VehiclesModel.plate_number.name,
                ExpensesModel.soongo_category.name,
            ]
        )[ExpensesModel.billing_date.name].transform('count')
        expenses_df = expenses_df[
            [
                VehiclesModel.plate_number.name,
                ExpensesModel.soongo_category.name,
                'nb_months',
                'count',
                VehicleContractsModel.contract_type.name,
            ]
        ].drop_duplicates()
        expenses_df['missing_payments'] = (
                expenses_df['nb_months'] - expenses_df['count']
            )
        expenses_df['missing_payments'] = (
            expenses_df['missing_payments'].mask(
                expenses_df['missing_payments'] < 0,
                0,
            )
        )
        expenses_df['missing_payments'] = (
            expenses_df['missing_payments'].mask(
                (
                    expenses_df[VehicleContractsModel.contract_type.name] ==
                    ContractType.short_medium_duration.value
                ),
                0,
            )
        )

        for cost_type in self.RECURRING_COSTS:
            cat_missing_payments = expenses_df.loc[
                (
                    expenses_df[ExpensesModel.soongo_category.name]
                    == cost_type
                ),
                ['count', 'missing_payments'],
            ]

            if cat_missing_payments['missing_payments'].any():
                nb_missing = cat_missing_payments['missing_payments'].sum()
                nb_total = len(cat_missing_payments)
                transaction_count = cat_missing_payments['count'].sum()

                self.logger.info(
                    'Table Expenses: There are %d plate_number with '
                    'missing %s mensualities out of %d, representing '
                    '%.2f%% of all cars and %.2f%% of all %s mensualities',
                    nb_missing,
                    cost_type,
                    nb_total,
                    nb_missing / nb_total * 100,
                    nb_missing / transaction_count * 100,
                    cost_type,
                )

        expenses_df = expenses_df.pivot(
            index=VehiclesModel.plate_number.name,
            columns=ExpensesModel.soongo_category.name,
            values='missing_payments',
        )
        expenses_df = expenses_df.rename(
            columns={
                col: 'missing_payment_' + col for col in expenses_df.columns
            },
        ).reset_index()
        assert expenses_df['plate_number'].is_unique

        return expenses_df

    def magnitude(self) -> pd.DataFrame:
        """ Check column magnitude

        :returns: None but logs share of failed values for each columns
        """
        col_set = set(self.MAGNITUDE_CHECKS.keys())
        check_results = []
        for table_name, table in self.input_tables:

            col_match = col_set.intersection(table.columns)
            for col in col_match:
                min_value, max_value = self.MAGNITUDE_CHECKS[col]
                error_series = (
                    (table[col] < min_value) | (table[col] > max_value)
                )
                check_results.append(
                    (table_name, col, error_series.sum() / len(error_series))
                )
                if error_series.any():
                    self.logger.info(
                        'Table %s: There are %d entries with '
                        'incorrect magnitudes for col %s out of %d, '
                        'representing %.2f%% of all entries',
                        table_name,
                        error_series.sum(),
                        col,
                        len(error_series),
                        error_series.sum() / len(error_series) * 100,
                    )

        magnitude_check_df = pd.DataFrame(
            check_results,
            columns=['table_name', 'column_name', 'share_errors'],
        )
        return magnitude_check_df

    def date_consistency(self) -> pd.DataFrame:
        """ Check date consistency

        :returns: None but logs share of inconsistent dates
        """
        vehicle_df = self.input_tables.get(VehiclesInputTable().name)
        vehicle_df = vehicle_df.drop(
            columns=[
                MileageReportsModel.mileage_date.name,
                MileageReportsModel.mileage.name,
            ],
        )
        expense_df = self.input_tables.get(ExpensesInputTable().name)
        mileage_df = self.input_tables.get(MileagesInputTable().name)
        association_df = self.input_tables.get(VehicleAssociationsInputTable().name)
        association_df = association_df.dropna(
            subset=[VehiclesModel.plate_number.name]
        )
        expense_df = expense_df.dropna(
            subset=[VehiclesModel.plate_number.name]
        )
        for date_var in [
            VehicleAssociationsModel.association_start_date.name,
            VehicleAssociationsModel.association_end_date.name,
        ]:
            association_df[date_var] = str_series_to_datetime(
                association_df[date_var]
            )

        # Lease start_date, entry into circulation_date, and lease end date
        consistency_df_lst = []
        for table, table_name, date_col in [
            (expense_df, 'expenses', ExpensesModel.billing_date.name),
            (mileage_df, 'mileage', MileageReportsModel.mileage_date.name),
        ]:
            combined_df = table.merge(
                right=vehicle_df,
                on=VehiclesModel.plate_number.name,
                validate='m:1',
                how='left',
            )
            if (
                CollaboratorsModel.soongo_collab_reference.name in combined_df.columns and
                not series_is_nan(
                    combined_df[CollaboratorsModel.soongo_collab_reference.name]
                ).all()
            ):
                date_df = self.regroup_association_df(
                    association_df=association_df,
                    regroup_cols=[
                        VehiclesModel.plate_number.name,
                        CollaboratorsModel.soongo_collab_reference.name,
                    ]
                )
                combined_df = combined_df.merge(
                    right=date_df,
                    on=[
                        VehiclesModel.plate_number.name,
                        CollaboratorsModel.soongo_collab_reference.name,
                    ],
                    validate='m:1',
                    how='left',
                )
            else:
                date_df = self.regroup_association_df(
                    association_df=association_df,
                    regroup_cols=[
                        VehiclesModel.plate_number.name,
                    ]
                )
                combined_df = combined_df.merge(
                    right=date_df,
                    on=[VehiclesModel.plate_number.name],
                    validate='m:1',
                    how='left',
                )

            combined_df[f'{table_name}_count'] = (
                pd.notna(combined_df[date_col])
            )
            if ExpensesModel.soongo_category.name in combined_df.columns:
                combined_df[f'{table_name}_rent_count'] = (
                    combined_df[ExpensesModel.soongo_category.name] ==
                    CostCategory.financial_rent.value
                ) & combined_df[f'{table_name}_count']
            else:
                combined_df[f'{table_name}_rent_count'] = False

            cols = [f'{table_name}_count', f'{table_name}_rent_count']

            for comp_col, comp_operator in self.DATE_COHERENCE_CHECKS.items():
                combined_df[f'{comp_col}_{table_name}_incoherence'] = (
                    combined_df[f'{table_name}_count'] &
                    comp_operator(
                        combined_df[date_col],
                        combined_df[comp_col],
                    ) & pd.notna(combined_df[comp_col])
                )
                combined_df[f'{comp_col}_{table_name}_rent_incoherence'] = (
                    combined_df[f'{comp_col}_{table_name}_incoherence'] &
                    combined_df[f'{table_name}_rent_count']
                )

                total_count = combined_df[f'{table_name}_count'].sum()
                error_count = combined_df[
                    f'{comp_col}_{table_name}_incoherence'
                ].sum()
                financial_rent_count = combined_df[
                    f'{comp_col}_{table_name}_rent_incoherence'
                ].sum()
                cols.extend(
                    [
                        f'{comp_col}_{table_name}_incoherence',
                        f'{comp_col}_{table_name}_rent_incoherence',
                    ]
                )

                if error_count:
                    self.logger.info(
                        'Table %s: There are %d entries incoherent with'
                        ' %s out of %d, including %d financial rents'
                        ' representing %.2f%% of all entries',
                        table_name,
                        error_count,
                        comp_col,
                        total_count,
                        financial_rent_count,
                        error_count / total_count * 100,
                    )

            consistency_df_lst.append(
                combined_df.groupby(
                    VehiclesModel.plate_number.name,
                )[cols].sum().reset_index()
            )

        consistency_df = consistency_df_lst[0].merge(
            right=consistency_df_lst[1],
            on=VehiclesModel.plate_number.name,
            how='outer',
            validate='1:1',
        )
        assert consistency_df[VehiclesModel.plate_number.name].is_unique

        return consistency_df

    def tco(
        self: typing.Self,
        year: int,
        social_security_tax_rate: float = 0.48,
        ikb_expense_rate: float = 0.3,
        tco_ratio_tolerance: float = 0.3,
        fuel_price_assumption: int = 2,
        professional_use_share: float = 0.7,
    ) -> pd.DataFrame:
        """ Compute and check tco consistency

        :returns: Dataframe of plate_numbers to consistency
        """
        # Get expense aggregates
        tco_df = self.input_tables.get(VehiclesInputTable().name).copy()
        expense_metrics = self.compute_expenses_metrics(
            expense_df=self.input_tables.get(ExpensesInputTable().name).copy(),
            year=year,
        )
        tco_df = tco_df.merge(
            right=expense_metrics,
            on=VehiclesModel.plate_number.name,
            how='left',
            validate='1:1',
            indicator=True,
        )
        assert (tco_df['_merge'] != 'right_only').all()
        tco_df = tco_df.drop('_merge', axis=1)

        # Get participation metric
        association_table = (
            self.input_tables.get(VehicleAssociationsInputTable().name).copy()
        )
        associations_df = self.get_association_metrics(
            associations_df=association_table,
            vehicle_df=self.input_tables.get(VehiclesInputTable().name).copy(),
            year=year,
            social_security_tax_rate=social_security_tax_rate,
        )
        tco_df = tco_df.merge(
            right=associations_df,
            on=VehiclesModel.plate_number.name,
            how='outer',
            validate='1:1',
        )

        # Get mileage
        mileage_table = self.input_tables.get(MileagesInputTable().name).copy()
        mileage_df = self.get_mileage_df(
            mileage_df=mileage_table,
            year=year,
        )
        tco_df = tco_df.merge(
            right=mileage_df,
            on=VehiclesModel.plate_number.name,
            how='outer',
            validate='1:1'
        )
        default_fuel_consumption = (
            tco_df[VehiclesModel.theoretical_fuel_consumption.name].mean()
        )
        tco_df[f'missing_fuel_spend_{year}'] = np.where(
            tco_df[f'total_energy_{year}'] < (
                tco_df[f'recorded_driven_mileage_{year}'] / 100
                * tco_df[VehiclesModel.theoretical_fuel_consumption.name].fillna(
                    default_fuel_consumption
                ) / fuel_price_assumption * professional_use_share
            ),
            1,
            0,
        )
        tco_df['nb_months'] = (
            tco_df[f'days_active_{year}'].floordiv(30)
        )
        tco_df[f'missing_mileage_{year}'] = (
            tco_df['nb_months'] - tco_df[f'mileage_count_{year}']
        )
        tco_df[f'missing_mileage_{year}'] = (
            tco_df[f'missing_mileage_{year}'].mask(
                tco_df[f'missing_mileage_{year}'] < 0,
                0,
            )
        )

        # Compute total_taxes
        taxes_df = self.get_taxes_df(
            taxes_df=self.input_tables.get(TaxesInputTable().name).copy(),
            year=year,
        )
        tco_df = tco_df.merge(
            right=taxes_df,
            on=VehiclesModel.plate_number.name,
            how='outer',
            validate='1:1'
        )
        tco_df[f'ikb_expense_based_taxes_{year}'] = (
            social_security_tax_rate * ikb_expense_rate *
            (
                tco_df[f'ikb_no_fuel_expense_based_{year}'] +
                tco_df[f'participation_{year}']  # negative participation
            )
        )
        tco_df[f'ikb_expense_based_taxes_{year}'] = (
            tco_df[f'ikb_expense_based_taxes_{year}'].mask(
                tco_df[f'ikb_expense_based_taxes_{year}'] < 0,
                0,
            )
        )
        tco_df[f'ikb_calculated_taxes_{year}'] = (
            tco_df[
                [
                    f'ikb_no_fuel_purchase_based_taxes_{year}',
                    f'ikb_expense_based_taxes_{year}',
                ]
            ].min(axis=1)
        )
        tco_df[f'total_taxes_{year}'] = tco_df[
            [
                f'ikb_calculated_taxes_{year}',
                f'calculated_amortization_taxes_{year}',
                TaxesModel.tax_vehicle_age.name,
                TaxesModel.tax_CO2_emission.name,
                TaxesModel.tax_corporate_vehicles.name,
                f'taxes_expense_{year}',
            ]
        ].sum(axis=1)

        # Ignore claims, unable to allocate them properly when associations
        # are missing
        tco_df[f'TCO_{year}'] = tco_df[
            [
                f'mileage_count_{year}',
                f'missing_mileage_{year}',
                f'missing_fuel_spend_{year}',
                f'total_insurance_costs_{year}',
                f'total_other_costs_{year}',
                f'total_energy_{year}',
                f'total_rent_{year}',
                f'total_taxes_{year}',
                f'participation_{year}',
            ]
        ].fillna(0).sum(axis=1)
        period_start, period_end = self.get_year_start_year_end(year)
        tco_df[f'vehicle_eq_full_time_{year}'] = (
            tco_df[f'days_active_{year}'] / (
                (period_end - period_start).days + 1
            )
        )
        tco_df[f'TCO_eq_full_time_{year}'] = (
            tco_df[f'TCO_{year}'] / tco_df[f'vehicle_eq_full_time_{year}']
        )
        tco_df['TCO_rent_ratio'] = (
            (tco_df[f'TCO_{year}'] - tco_df[f'total_other_costs_{year}'])
            / tco_df[f'total_rent_{year}'].mask(
                tco_df[f'total_rent_{year}'] <= 0,
                pd.NA,
            )
        )  # Exclude other costs, too volatile.
        tco_group_cols = [
            VehicleContractsModel.contract_type.name,
            VehiclesModel.fiscal_type.name
        ]

        # Fill in to compute mean on missing values
        for col in tco_group_cols:
            tco_df[col] = tco_df[col].fillna('NA')
        tco_df['median_TCO_rent_ratio'] = tco_df.groupby(
            [
                VehicleContractsModel.contract_type.name,
                VehiclesModel.fiscal_type.name
            ]
        )['TCO_rent_ratio'].transform('median')
        tco_df['TCO_rent_ratio_lower_bound'] = (
            tco_df['median_TCO_rent_ratio'] * (1 - tco_ratio_tolerance)
        )
        tco_df['TCO_rent_ratio_upper_bound'] = (
            tco_df['median_TCO_rent_ratio'] * (1 + tco_ratio_tolerance)
        )
        tco_df[f'unrealistic_tco_relative_{year}'] = np.where(
            (tco_df['TCO_rent_ratio'] < tco_df['TCO_rent_ratio_lower_bound']) |
            (tco_df['TCO_rent_ratio'] > tco_df['TCO_rent_ratio_upper_bound']),
            1,
            0
        )
        tco_df[f'rent_eq_full_fime{year}'] = (
            tco_df[f'total_rent_{year}'] / tco_df[f'vehicle_eq_full_time_{year}']
        )
        tco_df[f'unrealistic_tco_absolute_{year}'] = (
            self.gen_absolute_unrealistic_tco(
                rent_series=tco_df[f'rent_eq_full_fime{year}'],
                purchase_price_series=tco_df[VehiclesModel.rebate_price.name],
                lease_month_series=tco_df[VehicleContractsModel.lease_months.name],
            )
        )

        assert tco_df.plate_number.is_unique
        return tco_df[
            [
                VehiclesModel.plate_number.name,
                f'mileage_count_{year}',
                f'missing_mileage_{year}',
                f'missing_fuel_spend_{year}',
                f'total_insurance_costs_{year}',
                f'total_other_costs_{year}',
                f'total_energy_{year}',
                f'total_rent_{year}',
                f'total_taxes_{year}',
                f'participation_{year}',
                f'TCO_{year}',
                f'vehicle_eq_full_time_{year}',
                f'TCO_eq_full_time_{year}',
                f'unrealistic_tco_relative_{year}',
                f'unrealistic_tco_absolute_{year}',
            ]
        ]

    def collaborators(
        self: typing.Self,
        cutoff: float = 80.0,
    ) -> pd.DataFrame:
        """ Checks whether there are duplicated names in the collaborators
        table.

        :returns: collaborators dataframe with duplicate score risks
        """
        collaborators_df = self.input_tables.get(EmployeesInputTable().name).copy()

        collab_ids = collaborators_df[[CollaboratorsModel.soongo_collab_reference.name]]
        alternative_names = collaborators_df[CollaboratorsModel.alternative_names.name]
        names = collab_ids[CollaboratorsModel.soongo_collab_reference.name].str.split(
            ' ',
            expand=True,
        )
        score_matrices = [
            process.cdist(
                queries=names[col_label],
                choices=alternative_names,
                # partial_token returns 100 if substring entirely in choice
                scorer=fuzz.partial_token_sort_ratio,
                processor=utils.default_process,
            )
            for col_label in names.columns
        ]

        score_matrices = np.stack(score_matrices, axis=2)  # 3D matrix
        # fuzz returns match of None against x as 0, must be cast to null
        score_matrices[score_matrices == 0] = np.nan
        mean_score = np.nanmean(score_matrices, axis=2)  # Ignore nan
        collab_ids['scores'] = ''
        collab_ids['matched_names'] = ''
        for col_idx in range(mean_score.shape[1]):
            scored_name = collab_ids[CollaboratorsModel.soongo_collab_reference.name].at[col_idx]
            match_cond = (
                (mean_score[:, col_idx] > cutoff) &
                (collab_ids[CollaboratorsModel.soongo_collab_reference.name] != scored_name)
            )
            collab_ids['scores'] = np.where(
                match_cond,
                collab_ids['scores'] + self.stringify_score(
                    mean_score[:, col_idx]
                ),
                collab_ids['scores']
            )
            collab_ids['matched_names'] = np.where(
                match_cond,
                collab_ids['matched_names'] + f', {scored_name}',
                collab_ids['matched_names']
            )
        return collab_ids

    @staticmethod
    def stringify_score(float_array: np.array) -> np.array:
        """ Convert float score array to a string array of 1st decimal scores,
        comma separated.

        :param float_array: float numpy array

        :returns: string array of 'value, '
        """
        str_array = ['%.1f' % score for score in float_array]
        return np.char.add(str_array, ', ')

    @classmethod
    def compute_expenses_metrics(
        cls,
        expense_df: pd.DataFrame,
        year: int,
    ) -> pd.DataFrame:
        """ Compute the net total insurance costs component of the TCO

        :param expense_df: Dataframe of expense transactions
        :param period_start: start of the period
        :param period_end: end of the period

        :returns: updated Dataframe with additional component
        """
        period_start, period_end = cls.get_year_start_year_end(year)

        expense_df[ExpensesModel.billing_date.name] = str_series_to_datetime(
            expense_df[ExpensesModel.billing_date.name]
        )
        expense_df = expense_df.loc[
            (expense_df[ExpensesModel.billing_date.name] >= period_start) &
            (expense_df[ExpensesModel.billing_date.name] <= period_end)
        ]
        for metric_name, categories in cls.EXPENSE_METRICS.items():
            expense_df[metric_name + f'_{year}'] = (
                expense_df[ExpensesModel.net_amount.name].where(
                    expense_df[ExpensesModel.soongo_category.name].isin(
                        categories
                    ),
                    0
                )
            )

        output_cols = [
            f'{metric_name}_{year}'
            for metric_name in cls.EXPENSE_METRICS.keys()
        ]

        return expense_df.groupby(
            VehiclesModel.plate_number.name,
        )[output_cols].sum().reset_index()

    @classmethod
    def get_association_metrics(
        cls,
        associations_df: pd.DataFrame,
        vehicle_df: pd.DataFrame,
        year: int,
        corporate_tax_rate: float = 0.25,
        social_security_tax_rate: float = 0.48,
        ikb_purchase_rate: float = 0.09,
    ) -> pd.DataFrame:
        """
        Compute the net total insurance costs component of the TCO

        :param expense_df: Dataframe of expense transactions
        :param period_start: start of the period
        :param period_end: end of the period

        :returns: updated Dataframe with additional component
        """
        period_start, period_end = cls.get_year_start_year_end(year)
        associations_df[VehicleAssociationsModel.association_start_date.name] = (
            str_series_to_datetime(
                associations_df[VehicleAssociationsModel.association_start_date.name]
            )
        )
        associations_df[VehicleAssociationsModel.association_end_date.name] = (
            str_series_to_datetime(
                associations_df[VehicleAssociationsModel.association_end_date.name]
            )
        )

        # Drop out of range associations
        associations_df[VehicleAssociationsModel.association_end_date.name] = (
            associations_df[VehicleAssociationsModel.association_end_date.name].fillna(
                period_end,
            )
        )
        associations_df = associations_df.loc[
            (
                associations_df[VehicleAssociationsModel.association_end_date.name] >=
                period_start
            ) &
            (
                associations_df[VehicleAssociationsModel.association_start_date.name] <=
                period_end
            )
        ]

        # Correct start_date
        associations_df[VehicleAssociationsModel.association_start_date.name] = (
            associations_df[VehicleAssociationsModel.association_start_date.name].mask(
                associations_df[VehicleAssociationsModel.association_start_date.name] <
                period_start,
                period_start,
            )
        )

        # Correct end date
        associations_df[VehicleAssociationsModel.association_end_date.name] = (
            associations_df[VehicleAssociationsModel.association_end_date.name].mask(
                associations_df[VehicleAssociationsModel.association_end_date.name] >
                period_end,
                period_end,
            )
        )
        associations_df[f'days_active_{year}'] = (
            associations_df[VehicleAssociationsModel.association_end_date.name] -
            associations_df[VehicleAssociationsModel.association_start_date.name]
        ).dt.days + 1
        associations_df[f'participation_{year}'] = (
            associations_df[f'days_active_{year}'] *
            -associations_df[VehicleAssociationsModel.daily_participation.name]
        )  # recorded as negative value

        # Compute calculated amortization
        associations_df = associations_df.merge(
            right=vehicle_df,
            on=VehiclesModel.plate_number.name,
            how='left',
            validate='m:1',
        )
        associations_df['deductible_amortization'] = (  # Invariant
            associations_df[VehiclesModel.rebate_price.name] -
            np.select(
                [
                    associations_df[VehiclesModel.co2_per_km.name] >= 0.131,
                    associations_df[VehiclesModel.co2_per_km.name] >= 0.06,
                    associations_df[VehiclesModel.co2_per_km.name] >= 0.02,
                    associations_df[VehiclesModel.co2_per_km.name] >= 0,
                    pd.isna(associations_df[VehiclesModel.co2_per_km.name])
                ],
                [
                    9900,
                    18300,
                    20300,
                    30000,
                    9900,
                ],
            )
        )
        associations_df[f'calculated_amortization_taxes_{year}'] = (
            corporate_tax_rate * np.where(
                associations_df[f'days_active_{year}'] <= 5 * 365,
                (
                    associations_df[f'days_active_{year}'] / (5 * 365)
                    * associations_df['deductible_amortization']
                ),
                (
                    associations_df['deductible_amortization']
                ),
            )
        )
        associations_df[f'ikb_no_fuel_purchase_based_taxes_{year}'] = (
            social_security_tax_rate * ikb_purchase_rate * (
                associations_df[f'days_active_{year}'] / 365
                * associations_df[VehiclesModel.rebate_price.name]
                + associations_df[f'participation_{year}']
            )
        )
        associations_df[f'ikb_no_fuel_purchase_based_taxes_{year}'] = (
            associations_df[f'ikb_no_fuel_purchase_based_taxes_{year}'].mask(
                (
                    associations_df[f'ikb_no_fuel_purchase_based_taxes_{year}']
                    < 0
                ),
                0,
            )
        )
        associations_df = associations_df.groupby(
            VehiclesModel.plate_number.name
        )[
            [
                f'days_active_{year}',
                f'participation_{year}',
                f'calculated_amortization_taxes_{year}',
                f'ikb_no_fuel_purchase_based_taxes_{year}',
            ]
        ].sum().reset_index()
        return associations_df

    @classmethod
    def get_mileage_df(
        cls: typing.Self,
        mileage_df: pd.DataFrame,
        year: int,
    ) -> pd.DataFrame:
        period_start, period_end = cls.get_year_start_year_end(year)
        mileage_df[MileageReportsModel.mileage_date.name] = str_series_to_datetime(
            mileage_df[MileageReportsModel.mileage_date.name]
        )
        mileage_df = mileage_df.loc[
            (mileage_df[MileageReportsModel.mileage_date.name] >= period_start) &
            (mileage_df[MileageReportsModel.mileage_date.name] <= period_end),
            [
                VehiclesModel.plate_number.name,
                MileageReportsModel.mileage.name,
                MileageReportsModel.mileage_date.name,
            ]
        ]
        mileage_df['start_mileage'] = (
            mileage_df.groupby(
                VehiclesModel.plate_number.name
            )[MileageReportsModel.mileage.name].transform('min')
        )
        mileage_df['end_mileage'] = (
            mileage_df.groupby(
                VehiclesModel.plate_number.name
            )[MileageReportsModel.mileage.name].transform('max')
        )
        mileage_df[f'recorded_driven_mileage_{year}'] = (
            mileage_df['end_mileage'] - mileage_df['start_mileage']
        )
        mileage_df[f'mileage_count_{year}'] = (
            mileage_df.groupby(
                VehiclesModel.plate_number.name
            )[MileageReportsModel.mileage.name].transform('count')
        )

        return mileage_df[
            [
                VehiclesModel.plate_number.name,
                f'mileage_count_{year}',
                f'recorded_driven_mileage_{year}',
            ]
        ].drop_duplicates()

    @classmethod
    def get_taxes_df(
        cls: typing.Self,
        taxes_df: pd.DataFrame,
        year: int,
    ) -> pd.DataFrame:
        period_start, period_end = cls.get_year_start_year_end(year)
        taxes_df[ExpensesModel.billing_date.name] = str_series_to_datetime(
            taxes_df[ExpensesModel.billing_date.name]
        )
        taxes_df = taxes_df.loc[
            (taxes_df[ExpensesModel.billing_date.name] >= period_start) &
            (taxes_df[ExpensesModel.billing_date.name] <= period_end),
            [
                VehiclesModel.plate_number.name,
                TaxesModel.tax_vehicle_age.name,
                TaxesModel.tax_CO2_emission.name,
                TaxesModel.tax_corporate_vehicles.name,
            ]
        ]
        taxes_df = taxes_df.groupby(
            VehiclesModel.plate_number.name
        ).sum().reset_index()
        return taxes_df

    @classmethod
    def get_claims_df(
        cls,
        claims_df: pd.DataFrame,
        associations_table: pd.DataFrame,
        year: int,
    ):
        period_start, period_end = cls.get_year_start_year_end(year)
        claims_df[ClaimsModel.expense_date.name] = str_series_to_datetime(
            claims_df[ClaimsModel.expense_date.name]
        )
        claims_df = claims_df.loc[
            (claims_df[ClaimsModel.expense_date.name] >= period_start) &
            (claims_df[ClaimsModel.expense_date.name] <= period_end) &
            (claims_df[ClaimsModel.expense_type.name].isin(
                cls.FLEET_CLAIMS
            )),
            [
                CollaboratorsModel.soongo_collab_reference.name,
                ClaimsModel.expense_date.name,
                ExpensesModel.net_amount.name,
            ]
        ]
        claims_df[CollaboratorsModel.soongo_collab_reference.name] = (
            claims_df[CollaboratorsModel.soongo_collab_reference.name].astype(str)
        )
        claims_df = claims_df.groupby(
            [
                CollaboratorsModel.soongo_collab_reference.name,
                ClaimsModel.expense_date.name,
            ]
        ).sum().reset_index()
        associations_table[CollaboratorsModel.soongo_collab_reference.name] = (
            associations_table[CollaboratorsModel.soongo_collab_reference.name].astype(str)
        )
        claims_df = claims_df.merge(
            right=associations_table,
            on=CollaboratorsModel.soongo_collab_reference.name,
            how='right',
            validate='m:m',
        )
        claims_df[VehicleAssociationsModel.association_start_date.name] = str_series_to_datetime(
            claims_df[VehicleAssociationsModel.association_start_date.name]
        )
        claims_df[VehicleAssociationsModel.association_end_date.name] = str_series_to_datetime(
            claims_df[VehicleAssociationsModel.association_end_date.name]
        )
        claims_df = claims_df.loc[
            (
                claims_df[ClaimsModel.expense_date.name] >=
                claims_df[VehicleAssociationsModel.association_start_date.name]
            ) &
            (
                claims_df[ClaimsModel.expense_date.name] <=
                claims_df[VehicleAssociationsModel.association_end_date.name].fillna(
                    claims_df[ClaimsModel.expense_date.name]
                )
            )
        ]
        claims_df = claims_df.sort_values(
            by=[
                VehicleAssociationsModel.association_start_date.name,
                VehicleAssociationsModel.association_end_date.name,
            ],
            ascending=[True, False],
        )
        claims_df = claims_df.drop_duplicates(
            subset=[
                CollaboratorsModel.soongo_collab_reference.name,
                ClaimsModel.expense_date.name,
            ],
        )
        claims_df = claims_df.groupby(
            VehiclesModel.plate_number.name
        )[ExpensesModel.net_amount.name].sum().reset_index()
        claims_df = claims_df.rename(columns={
            ExpensesModel.net_amount.name: f'total_fleet_claims_{year}',
        })
        return claims_df

    @staticmethod
    def get_year_start_year_end(
        year: int
    ) -> typing.Tuple[pd.DatetimeTZDtype, pd.DatetimeTZDtype]:
        period_start: pd.DatetimeTZDtype = pd.to_datetime(
            f'{year}-01-01',
            yearfirst=True,
        )
        period_end: pd.DatetimeTZDtype = pd.to_datetime(
            f'{year}-12-31',
            yearfirst=True,
        )
        return period_start, period_end

    @staticmethod
    def regroup_association_df(
        association_df: pd.DataFrame,
        regroup_cols: typing.List[str],
    ) -> pd.DataFrame:
        """ Regroup association_df using the passed regroup columns

        :param association_df: pandas dataframe with vehicle / collaborator
        association data
        :param regroup_cols: columns to regroup the association_df on.
        """
        assert set(regroup_cols).issubset(association_df.columns)
        association_df[VehicleAssociationsModel.association_start_date.name] = (
            association_df.groupby(
                regroup_cols
            )[VehicleAssociationsModel.association_start_date.name].transform('min')
        )
        association_df[VehicleAssociationsModel.association_end_date.name] = (
            association_df.groupby(
                regroup_cols
            )[VehicleAssociationsModel.association_end_date.name].transform('max')
        )
        return association_df[
            regroup_cols + [
                VehicleAssociationsModel.association_start_date.name,
                VehicleAssociationsModel.association_end_date.name,
            ]
        ].drop_duplicates()

    @staticmethod
    def gen_absolute_unrealistic_tco(
        rent_series: pd.Series,
        purchase_price_series: pd.Series,
        lease_month_series: pd.Series,
        purchase_price_bounds: typing.Tuple[float, float] = (1*10**4, 5*10**4),
    ) -> np.array:
        """ Generate unrealistic tco indicator in absolute terms

        Rental companies are supposed to recover their investment
        (purchase price) in 5 years or over the lease length, whichever is
        longer, as well as earn an interest over that investment. This check
        checks whether the total rent is aligned with this

        """
        amortization_series = lease_month_series.mask(
            pd.isna(lease_month_series) | (lease_month_series < 60),
            60,  # Even in the event of shorter term rentals amortization is 5 years
        )
        low_financial_rent_bound = purchase_price_series.fillna(
            purchase_price_bounds[0]
        ) / amortization_series * 12 + purchase_price_series.fillna(
            purchase_price_bounds[0]
        ) * 0.04
        high_financial_rent_bound = purchase_price_series.fillna(
            purchase_price_bounds[1]
        ) / amortization_series * 12 + purchase_price_series.fillna(
            purchase_price_bounds[1]
        ) * 0.06

        unrealistic_tco = np.where(
            pd.notna(rent_series) &
            pd.notna(low_financial_rent_bound) &
            pd.notna(high_financial_rent_bound)
            & (
                (rent_series < low_financial_rent_bound) |
                (rent_series > high_financial_rent_bound)
            ),
            1,
            0,
        )
        return unrealistic_tco


def parse_args():
    """ Parse arguments passed to the TableChecker
    """
    parser = argparse.ArgumentParser(
        description='Anonymize tables in a folder.'
    )

    parser.add_argument(
        '-t',
        '--target',
        type=str,
        help='Path to the folder containing tables to check.',
    )
    parser.add_argument(
        '-o',
        '--output',
        type=str,
        help='Path to the folder where to store the check output.',
    )

    # Check args
    args = parser.parse_args()

    for folder in (args.target, args.output):
        if not os.path.isdir(os.path.expanduser(folder)):
            raise ValueError(
                f'Unexistent path passed as argument: {folder}'
            )

    for table in TABLE_LST:
        if not os.path.exists(
            os.path.join(
                os.path.expanduser(args.target),
                table.name + '_table.csv',
            )
        ):
            raise ValueError(
                f'The passed target folder {args.target} does not have a table'
                f' {table.name}_table'
            )
    return args


def str_series_to_datetime(
    str_series: pd.Series,
) -> pd.Series:
    # str_series = str_series.mask(series_is_nan(str_series), pd.NaT)
    str_series = convert_string(str_series)
    str_series = str_series.mask(
        (str_series.str.len() == 10) & ~series_is_nan(str_series),
        str_series + ' 00:00:00',
    )
    return pd.to_datetime(
        str_series,
        format=r'%Y-%m-%d %H:%M:%S',
    )


if __name__ == '__main__':
    args = parse_args()
    logger = gen_logger('data_checker')
    input_tables = InputTables(args.target)
    checker = TableChecks(
        input_tables=input_tables,
        logger=logger,
        output_folder=args.output,
    )
    checker.run_checks()
