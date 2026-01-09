""" Expense table utility functions"""
import logging

import pandas as pd

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (CollaboratorsModel,
                                     ExpensesModel,
                                     VehiclesModel)
from soongo_data.utils.enums import (ExpenseType, FiscalType, FuelTypes,
                                     InsurancePremiums, RentCategory, TravelTypes)
from soongo_data.utils.fetch import fetch_vehicle_data, get_org_param


def non_deduc_vat_categories() -> set[str]:
    return {
        cat.value for cat in RentCategory
    }.union(
        {
            ExpenseType.taxi.value,
            ExpenseType.public_transportation.value,
            ExpenseType.train.value,
            ExpenseType.plane.value,
            ExpenseType.car_rental.value,
            ExpenseType.light_transportation_rental.value,
        }
    ).union(
        {
            TravelTypes.air.value,
            TravelTypes.rail.value,
            TravelTypes.rental_car.value
        }
    )


def infer_amounts_and_tax(
    df: pd.DataFrame,
    logger: logging.Logger,
    connector_data: ConnectorData,
    category_col: str,
    vat_assumption: float = 0.2,
) -> pd.DataFrame:
    """ Infer amount tax inc, tax, excluded, net, and VAT from available
    information in df.

    :param df: DataFrame with amount information must have at least one of
    amount_tax_exc or amount_tax_inc
    logger: logger
    :param connector_data: Connector Data for this organization
    :param vat_assumption: Assumed VAT rate to use when not available
    :param category_col: name of the category variable in df
    """
    amount_cols = {
        ExpensesModel.amount_tax_inc.name,
        ExpensesModel.amount_tax_exc.name,
    }
    available_cols = amount_cols.intersection(df.columns)
    if not available_cols:
        raise ValueError('May not infer if no amount data available')

    # Fill in tax_inc and tax_exc
    if ExpensesModel.vat_value.name in df.columns:
        if ExpensesModel.amount_tax_inc.name not in available_cols:
            df[ExpensesModel.amount_tax_inc.name] = (
                df[ExpensesModel.amount_tax_exc.name] +
                df[ExpensesModel.vat_value.name]
            ).round(2)
        if ExpensesModel.amount_tax_exc.name not in available_cols:
            df[ExpensesModel.amount_tax_exc.name] = (
                df[ExpensesModel.amount_tax_inc.name] -
                df[ExpensesModel.vat_value.name]
            ).round(2)

    if ExpensesModel.vat_value.name not in df.columns:
        is_insurance = (
            df[category_col].isin(
                [
                    insurance_cat.value for insurance_cat
                    in InsurancePremiums
                ]
            )
        )

        if ExpensesModel.amount_tax_inc.name not in available_cols:
            df[ExpensesModel.amount_tax_inc.name] = (
                (1 + vat_assumption) * df[ExpensesModel.amount_tax_exc.name]
            ).round(2)
            df[ExpensesModel.amount_tax_inc.name] = (
                df[ExpensesModel.amount_tax_inc.name].mask(
                    is_insurance,
                    df[ExpensesModel.amount_tax_exc.name],
                )
            )
        if ExpensesModel.amount_tax_exc.name not in available_cols:
            df[ExpensesModel.amount_tax_exc.name] = (
                df[ExpensesModel.amount_tax_inc.name] / (1 + vat_assumption)
            ).round(2)
            df[ExpensesModel.amount_tax_exc.name] = (
                df[ExpensesModel.amount_tax_exc.name].mask(
                    is_insurance,
                    df[ExpensesModel.amount_tax_inc.name],
                )
            )

    # Fill in values for amount_tax_exc, amount_tax_inc and vat_amount
    df[ExpensesModel.amount_tax_inc.name] = (
        df[ExpensesModel.amount_tax_inc.name].fillna(
            value=(
                (1 + vat_assumption) * df[ExpensesModel.amount_tax_exc.name]
            ).round(2),
        )
    )
    df[ExpensesModel.amount_tax_exc.name] = (
        df[ExpensesModel.amount_tax_exc.name].fillna(
            value=(
                df[ExpensesModel.amount_tax_inc.name] / (1 + vat_assumption)
            ).round(2),
        )
    )
    df[ExpensesModel.vat_value.name] = (
        df[ExpensesModel.amount_tax_inc.name] -
        df[ExpensesModel.amount_tax_exc.name]
    ).round(2)

    # Fill in deductible_vat
    no_vat_deduct = get_org_param(
        organization_name=connector_data.organization_name,
        param_name='no_tva_deduc'
    )
    if no_vat_deduct:
        df[ExpensesModel.deductible_vat.name] = 0.0
    else:
        calculated_deduc_vat = compute_deductible_vat(
                df=df,
                connector_data=connector_data,
                logger=logger,
                category_col=category_col,
            )

        if ExpensesModel.deductible_vat.name not in df.columns:
            df[ExpensesModel.deductible_vat.name] = calculated_deduc_vat
        else:
            df[ExpensesModel.deductible_vat.name] = (
                df[ExpensesModel.deductible_vat.name].where(
                    pd.notna(df[ExpensesModel.deductible_vat.name]),
                    calculated_deduc_vat,
                )
            )

    # Fill in net amount
    if ExpensesModel.net_amount.name not in df.columns:
        df[ExpensesModel.net_amount.name] = (
            df[ExpensesModel.amount_tax_inc.name] -
            df[ExpensesModel.deductible_vat.name]
        ).round(2)
    else:
        df[ExpensesModel.net_amount.name] = df[ExpensesModel.net_amount.name].fillna(
            value=(
                df[ExpensesModel.amount_tax_inc.name] -
                df[ExpensesModel.deductible_vat.name]
            ).round(2),
        )
    return df


def compute_deductible_vat(
    df: pd.DataFrame,
    connector_data: ConnectorData,
    logger: logging.Logger,
    category_col: str,
) -> pd.Series:
    """ Computes deductible vat for each row, based on vehicle fiscal type and
    assignment as well as SoonGoCategory, if available.

    :param df: Pandas Dataframe for which the deductible vat must be computed
    :param connector_data: Connector Data for this organization
    :param logger: logger
    :param category_col: name of the category variable in df

    :returns: pd Series of float deductible vat values. DataFrame df also
        modified in place.
    """
    if ExpensesModel.vat_value.name not in df.columns:
        raise ValueError(
            'vat_amount is required to compute deductible_vat. '
            'See infer_amounts_and_tax.'
        )
    if (VehiclesModel.fiscal_type.name not in df.columns) or df[VehiclesModel.fiscal_type.name].isna().any():

        if CollaboratorsModel.soongo_collab_reference.name in df.columns:
            logger.warning(
                'Fetching fiscal type from soongo_collab_reference not implemented!'
            )
            """
            df = fetch_plate_from_collab(
                df=df,
                connector_data=connector_data,
                logger=logger,
                date_var=date_var,
            )
            """
        # If employee_id available then plate_number added by previous lines
        if VehiclesModel.plate_number.name in df.columns:
            df = fetch_vehicle_data(
                df=df,
                cols_to_fetch={VehiclesModel.fiscal_type.name, },
                connector_data=connector_data,
                logger=logger,
            )
            is_vu = (
                df[VehiclesModel.fiscal_type.name].isin(
                    [
                        FiscalType.utility_car.value,
                        FiscalType.other.value,
                    ]
                )
            ) & pd.notna(df[VehiclesModel.fiscal_type.name])

        else:
            logger.warning(
                'No plate_number or employee_id information. '
                'Assuming not exempt'
            )
            is_vu = pd.Series(False, df.index)

    else:
        is_vu = (
            df[VehiclesModel.fiscal_type.name].isin(
                [
                    FiscalType.utility_car.value,
                    FiscalType.other.value,
                ]
            )
        ) & pd.notna(df[VehiclesModel.fiscal_type.name])

    not_rent = ~df[category_col].isin(
        non_deduc_vat_categories()
    )
    deduc_vat = df[ExpensesModel.vat_value.name].where(
        is_vu | not_rent,
        0.0,
    )

    is_fuel = df[category_col].isin(
        [fuel_type.value for fuel_type in FuelTypes] + [ExpenseType.fuel.value]
    )
    # Electricity is fully deductible
    electric_deduc = (
        (df[category_col] == FuelTypes.electricity.value)
    )

    deduc_vat = deduc_vat.mask(
        ~is_vu & is_fuel & ~electric_deduc,
        (0.8 * df[ExpensesModel.vat_value.name]).round(2),
    )

    return deduc_vat


def detect_exceptional_rents(
    df: pd.DataFrame,
    logger: logging.Logger,
) -> pd.Series:
    """ Detect exceptional rents based on amount_tax_exc > 1000

    :param df: DataFrame with expense data
    :param logger: logger

    :returns: pd Series of boolean values indicating if rent is exceptional
    """
    if ExpensesModel.soongo_category.name not in df.columns:
        raise ValueError('soongo_category column required to detect rents')
    if ExpensesModel.amount_tax_exc.name not in df.columns:
        raise ValueError('amount_tax_exc column required to detect exceptional rents')

    is_rent = df[ExpensesModel.soongo_category.name].isin(
        [rent_cat.value for rent_cat in RentCategory]
    )
    is_exceptional = is_rent & (df[ExpensesModel.amount_tax_exc.name] > 1000)

    if is_exceptional.any():
        logger.info(
            f'Detected {is_exceptional.sum()} exceptional rents '
            '(amount_tax_exc > 1000)'
        )
    else:
        logger.info('No exceptional rents detected')

    return is_exceptional
