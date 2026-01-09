import pytz
import typing
from datetime import datetime

import numpy as np
import pandas as pd

from soongo_data.data_models import ExpensesModel, VehicleContractsModel
from soongo_data.utils.enums import (CostCategory, InsurancePremiums,
                                     RentCategory)

recurring_costs_lst = [
    rent.value for rent in RentCategory
] + [
    premium.value for premium in InsurancePremiums
]


amount_cols = {
    ExpensesModel.amount_tax_exc.name,
    ExpensesModel.amount_tax_inc.name,
    ExpensesModel.vat_value.name,
    ExpensesModel.deductible_vat.name,
}


rent_cost_dict = {
    CostCategory.financial_rent.value: {
        VehicleContractsModel.financial_rent_tax_exc.name: ExpensesModel.amount_tax_exc.name,
        VehicleContractsModel.financial_rent_ttc.name: ExpensesModel.amount_tax_inc.name,
    },
    CostCategory.rent_management_fees.value: {
        VehicleContractsModel.management_fee_rent_tax_exc.name: ExpensesModel.amount_tax_exc.name,
        VehicleContractsModel.management_fee_rent_ttc.name: ExpensesModel.amount_tax_inc.name,
    },
    CostCategory.rent_maintenance.value: {
        VehicleContractsModel.maintenance_rent_tax_exc.name: ExpensesModel.amount_tax_exc.name,
        VehicleContractsModel.maintenance_rent_ttc.name: ExpensesModel.amount_tax_inc.name,
    },
    CostCategory.rent_telematic.value: {
        VehicleContractsModel.telematics_rent_tax_exc.name: ExpensesModel.amount_tax_exc.name,
        VehicleContractsModel.telematics_rent_ttc.name: ExpensesModel.amount_tax_inc.name,
    },
    CostCategory.rent_tires.value: {
        VehicleContractsModel.tires_rent_tax_exc.name: ExpensesModel.amount_tax_exc.name,
        VehicleContractsModel.tires_rent_ttc.name: ExpensesModel.amount_tax_inc.name,
    },
    CostCategory.rent_fuel_card.value: {
        VehicleContractsModel.fuel_card_management_fee_rent_tax_exc.name: ExpensesModel.amount_tax_exc.name,
        VehicleContractsModel.fuel_card_management_fee_rent_ttc.name: ExpensesModel.amount_tax_inc.name,
    },
    CostCategory.rent_financial_loss.value: {
        VehicleContractsModel.financial_loss_rent_tax_exc.name: ExpensesModel.amount_tax_exc.name,
        VehicleContractsModel.financial_loss_rent_ttc.name: ExpensesModel.amount_tax_inc.name,
    },
    CostCategory.rent_assistance.value: {
        VehicleContractsModel.assistance_rent_tax_exc.name: ExpensesModel.amount_tax_exc.name,
        VehicleContractsModel.assistance_rent_ttc.name: ExpensesModel.amount_tax_inc.name,
    },
    CostCategory.rent_others.value: {
        VehicleContractsModel.other_rent_tax_exc.name: ExpensesModel.amount_tax_exc.name,
        VehicleContractsModel.other_rent_ttc.name: ExpensesModel.amount_tax_inc.name,
    },
}


def extrapolate_expense_from_rents(
    rent_df: pd.DataFrame,
    id_cols: typing.List[str],
    start_col: str,
    end_col: str,
    date_col: str = ExpensesModel.billing_date.name,
    period_increment: pd.DateOffset = pd.DateOffset(months=1),
    max_date: datetime = datetime.now(tz=pytz.timezone("Europe/Paris")),
) -> pd.DataFrame:
    """ Generate extrapolated expenses from a DataFrame indicating recurring
        cost values.

    :param rent_df: base dataframe with rent information to extrapolate from
    :param id_cols: columns for which the cost should occur every month start
    :param start_col: str col name of the column indicating when does the
        recurring costs starts
    :param end_col: str col_name of the column indicating when does the
        recurring costs end
    :param date_col: str column name of the date column; by default billing
        date.
    :param period_increment: DataOffset indicating how often does the recurring
        cost repeat.
    :param max_date: max date to continue the extrapolation until

    :returns: an extrapolated DataFrame where the recurring costs (e.g. rents)
        are repeated every month start for the given id cols between the
        specified start_col and end_col dates.
    """
    max_end_date = rent_df[end_col].fillna(max_date).mask(
        rent_df[end_col].fillna(max_date) > max_date,
        max_date,
    ).max()
    df_lst = []
    for cost_category, col_dict in rent_cost_dict.items():

        available_cols = set(col_dict.keys()).intersection(rent_df.columns)

        if not available_cols:
            continue

        current_date = rent_df[start_col].copy()
        while current_date.min() < max_end_date:

            expense_df = rent_df.copy()
            expense_df[ExpensesModel.soongo_category.name] = cost_category
            expense_df[date_col] = current_date
            for col_name in available_cols:
                expense_df[col_dict[col_name]] = rent_df[col_name]
            df_lst.append(
                expense_df.loc[
                    (
                        (current_date <= expense_df[end_col].fillna(max_date)) &
                        (current_date < max_date) &
                        pd.notna(rent_df[col_name])
                    ),
                    (
                        id_cols +
                        [date_col, ExpensesModel.soongo_category.name] +
                        [col_dict[col_name] for col_name in available_cols]
                    )
                ]
            )
            current_date += period_increment

    if not df_lst:
        return pd.DataFrame(
            columns=(
                id_cols +
                [date_col, ExpensesModel.soongo_category.name] +
                list(amount_cols)
            )
        )

    return pd.concat(
        df_lst,
        axis=0,
    )


def fill_expense_gaps(
    expense_df: pd.DataFrame,
    id_cols: typing.List[str],
    start_col: str,
    end_col: str,
    date_col: str = ExpensesModel.billing_date.name,
    period_alias: str = 'M',
    max_date: datetime = datetime.now(),
):
    """ Fill recurring expense_gaps in an expense dataframe.

    :param expense_df: base dataframe with incomplete expense information
    :param id_cols: columns for which the cost should occur every month start
    :param start_col: str col name of the column indicating when does the
        recurring costs starts
    :param end_col: str col_name of the column indicating when does the
        recurring costs end
    :param date_col: str column name of the date column; by default billing
        date.
    :param period_alias: a string indicating the time series frequencies.
        Default to monthly 'M'. See https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#timeseries-offset-aliases
    :param max_date: max date to continue the extrapolation until

    :returns: an extrapolated DataFrame where the gap in recurring costs
        (e.g. rents or insurance premium payments) are completed
    """
    start_date = expense_df[start_col].min()
    end_date = np.min([expense_df[end_col].max(), max_date])
    df_lst = [expense_df]
    available_amount_cols = list(amount_cols.intersection(expense_df.columns))
    for recurring_cost in recurring_costs_lst:
        recurring_df = expense_df.loc[
            expense_df[ExpensesModel.soongo_category.name] == recurring_cost
        ]

        if not recurring_df.empty:
            recurring_df['period'] = recurring_df[date_col].dt.to_period(period_alias)
            monthly_df = recurring_df.groupby(
                id_cols + [
                    'period',
                    ExpensesModel.soongo_category.name,
                    start_col,
                    end_col,
                ],
                dropna=False,
            )[available_amount_cols].sum().reset_index()
            mean_amount_df = monthly_df.groupby(
                id_cols + [
                    start_col,
                    end_col,
                    ExpensesModel.soongo_category.name,
                ],
                dropna=False,
            )[available_amount_cols].median().reset_index()  # TODO: Consider something better like take latest of update based on previous actual value

            for date in pd.date_range(
                start=start_date,
                end=end_date,
                freq=period_alias,
            ):
                mean_amount_df[date_col] = date
                is_available = monthly_df.loc[
                    (
                        monthly_df['period'].dt.month == date.month
                    ) & (
                        monthly_df['period'].dt.year == date.year
                    ),
                    id_cols,
                ]
                mean_amount_df = mean_amount_df.merge(
                    is_available,
                    on=id_cols,
                    how='left',
                    validate='1:1',
                    indicator=True,
                )

                final_df = mean_amount_df.loc[
                    (mean_amount_df[date_col] >= mean_amount_df[start_col])
                    &
                    (mean_amount_df[date_col] <= mean_amount_df[end_col])
                    & (mean_amount_df['_merge'] == 'left_only'),  # Don't duplicate if already there
                    id_cols + available_amount_cols + [
                        ExpensesModel.soongo_category.name,
                        ExpensesModel.billing_date.name,
                    ] + [  # TEMP
                        VehicleContractsModel.lease_start_date.name,
                        VehicleContractsModel.lease_end_date.name,
                    ]
                ]

                df_lst.append(final_df)

                mean_amount_df.drop('_merge', axis=1, inplace=True)

    combined_df = pd.concat(df_lst, axis=0)
    assert len(combined_df) > len(expense_df)
    return combined_df
