import logging
import re
import typing
from collections import Counter

import numpy as np
import pandas as pd

from soongo_data.data_models import (CollaboratorsModel, ExpensesModel,
                                     SoonGoRecordsModel)
from soongo_data.data_models.base import DataColumn
from soongo_data.utils.enums import SynchronizationTypes
from soongo_data.utils.type import (NamesConverter, convert_string,
                                    series_is_nan, str_is_nan, get_dtype_null)

RECORD_COLS = [
    SoonGoRecordsModel.connector_name.name,
    SoonGoRecordsModel.source_dataset.name,
    SoonGoRecordsModel.source_table.name,
    SoonGoRecordsModel.synchronisation_type.name,
]


def check_no_dup_values(iterable: typing.Iterable):
    """ Check no duplicate values in a passed iteratble

    :param iterable: Iterable whose values should all be unique

    :raises ValueError: if values are not all unique
    """
    if len(set(iterable)) < len(iterable):
        duplicated_values = [
            value for value, count in Counter(iterable).items()
            if count > 1
        ]
        raise ValueError(
            'Passed iterable contains duplicated values: '
            f'{duplicated_values}'
        )


def set_record_cols(
    df: pd.DataFrame,
    connector_name: str,
    source_dataset: str,
    source_table: str,
    synchronization_type: SynchronizationTypes,
) -> pd.DataFrame:
    df[RECORD_COLS] = (
        connector_name, source_dataset, source_table, synchronization_type
    )
    for col in RECORD_COLS:
        df[col] = convert_string(df[col])
        assert not str_is_nan(df[col]).any()

    return df


def check_columns(
    df: pd.DataFrame,
    col_lst: typing.List[DataColumn],
    organization_name: str,
) -> pd.DataFrame:
    handle_duplicate_cols(raw_df=df)

    for table_col in col_lst:

        try:
            if table_col.name not in df.columns:

                if table_col.optional:
                    df[table_col.name] = get_dtype_null(table_col.dtype)
                    continue
                else:
                    raise KeyError(
                        f'Required column {table_col.name} not found in '
                        f'provided DataFrame with columns {df.columns}'
                    )

            if table_col.post_processing:
                df[table_col.name] = table_col.post_processing(
                    df[table_col.name]
                )

            df[table_col.name] = df[table_col.name].astype(table_col.dtype)

        except (ValueError, TypeError, AttributeError) as error:
            raise TypeError(
                f'An error was met whilst converting column '
                f'{table_col.name} of type {df[table_col.name].dtype} to '
                f'{table_col.dtype}: {error}'
            )

    name_cols = {
        CollaboratorsModel.firstname.name,
        CollaboratorsModel.lastname.name,
    }
    if (
        name_cols.issubset(df.columns) and
        CollaboratorsModel.employee_full_name.name not in df.columns
    ):
        df[CollaboratorsModel.employee_full_name.name] = (
            NamesConverter(organization_name)(
                df[CollaboratorsModel.firstname.name]
                + ' ' +
                df[CollaboratorsModel.lastname.name]
            )
        )
    if CollaboratorsModel.employee_full_name.name in df.columns:
        df[CollaboratorsModel.employee_full_name.name] = NamesConverter(organization_name)(
            df[CollaboratorsModel.employee_full_name.name]
        )

    return df


def get_record_date(
    data_df: pd.DataFrame,
    record_dates: typing.List[str],
) -> pd.DataFrame:
    """ Add a record date to a DataFrame to indicate the minimum time at
        which each row was recorded. This info is used for deduplication.

    :param data_df: DataFrame to date each row for

    :returns: data_df with an additional record_date column
    """
    if not record_dates:
        data_df[SoonGoRecordsModel.record_date.name] = pd.NaT
    else:
        data_df[SoonGoRecordsModel.record_date.name] = pd.to_datetime(
            data_df[record_dates].max(
                axis=1
            )
        )
    return data_df


def handle_duplicate_cols(raw_df: pd.DataFrame) -> None:
    """ Handle duplicate columns in raw dataframe

    :param raw_df: imported DataFrame with possibly duplicated columns

    :raises ValueError: if multiple columns share the same name but contain
        different values

    :returns: None, but drops duplicate columns which contain the same values
    """
    dup_cols = [
        (col, re.search(r'(.*).*\.\d+$', str(col)).group(1))
        for col in raw_df.columns
        if re.search(r'(.*).*\.\d+$', str(col))
    ]

    for col, root_col in dup_cols:

        if root_col in raw_df.columns:

            # Handle Immat. with or without '-' format. Prefer with '-'
            if root_col == 'Immat.':
                sanitized_col = raw_df[col].str.replace('-', '')
                sanitized_root = raw_df[root_col].str.replace('-', '')

                if (sanitized_root == sanitized_col).all():

                    if raw_df[col].str.contains('-').any() is False:
                        raw_df.drop(col, axis=1, inplace=True)

                    else:
                        raw_df.drop(root_col, axis=1, inplace=True)
                        raw_df.rename(columns={col: root_col}, inplace=True)

                else:
                    raise ValueError(
                        'Multiple Immat. columns with different values'
                    )

            elif (raw_df[col].fillna(0) != raw_df[root_col].fillna(0)).any():
                raise ValueError(
                    f'Multiple cols named {root_col} have different values'
                )

            else:
                raw_df.drop(col, axis=1, inplace=True)


def check_col_matching(
    gac_col_lst: typing.List[DataColumn],
    raw_df: pd.DataFrame,
    logger: logging.Logger,
) -> None:
    """ Check columns matching between provided DataColumn list and dataframe

    :param gac_col_lst: list of DataColumns
    :param raw_df: import pandas DataFrame

    :raises ValueError: if gac_col_lst does not match raw_df columns
    """
    expected_col_names = {gac_col.raw_name for gac_col in gac_col_lst}
    actual_col_names = set(raw_df.columns).difference(
        {SoonGoRecordsModel.sheet_name.name}  # Added before check
    )
    if expected_col_names != actual_col_names:
        missing_expected = expected_col_names.difference(actual_col_names)
        unexpected_actual = actual_col_names.difference(expected_col_names)
        empty_unexpected = {
            col for col in unexpected_actual
            if (
                pd.api.types.is_numeric_dtype(raw_df[col]) and
                (raw_df[col] == 0).all() and pd.notna(raw_df[col]).any()
            ) or series_is_nan(raw_df[col]).all()
        }
        if unexpected_actual != empty_unexpected:
            raise ValueError(
                f'Expected columns {missing_expected} but missing and'
                f' found {unexpected_actual.difference(empty_unexpected)} but '
                f'not expected, as well as {len(empty_unexpected)} empty '
                f'columns: {empty_unexpected}'
            )
        else:
            logger.warning(
                'Dropping %d empty columns not in the DataColumn list',
                len(empty_unexpected),
            )
            raw_df.drop(list(empty_unexpected), axis=1, inplace=True)


def check_vat_consistency(expense_df: pd.DataFrame) -> None:
    """ Helper function which checks whether tax_exc, tax_inc, and VAT
    amount are consistent. Helps detects parsing errors, notably with OCR.

    :param expense_df: Pandas DataFrame with a amount_tax_exc,
        amount_tax_inc, and a vat_amount or vat_rate column.

    :raises ValueError: if necessary Columns not available or values do not
    match.

    :returns: None but checks that expense_df values are consistent
    """
    req_values = {
        ExpensesModel.amount_tax_exc.name,
        ExpensesModel.amount_tax_inc.name,
    }
    opt_values = {
        ExpensesModel.vat_value.name,
        ExpensesModel.vat_rate.name,
    }
    if not req_values.issubset(expense_df.columns):
        raise ValueError(
            f'Checking VAT consistency requires both {req_values} but '
            f'passed df only contains {expense_df.columns}'
        )

    vat_cols = opt_values.intersection(expense_df.columns)
    if not vat_cols:
        raise ValueError(
            f'Checking VAT consistency requires one of {opt_values} but'
            f'passed df only contains {expense_df.columns}'
        )

    if ExpensesModel.vat_value.name in vat_cols:
        vat_amount = expense_df[ExpensesModel.vat_value.name]

    else:
        vat_amount = (
            expense_df[ExpensesModel.amount_tax_inc.name] *
            expense_df[ExpensesModel.vat_rate.name] / 100
        )

    consistent_values = (
        np.isclose(
            expense_df[ExpensesModel.amount_tax_inc.name],
            (
                expense_df[ExpensesModel.amount_tax_exc.name] +
                vat_amount
            )
        ) | series_is_nan(expense_df[ExpensesModel.amount_tax_inc.name]) |
        series_is_nan(expense_df[ExpensesModel.amount_tax_exc.name]) |
        series_is_nan(vat_amount)
    )
    if not consistent_values.all():
        examples = expense_df.loc[
            ~consistent_values,
            [
                ExpensesModel.amount_tax_exc.name,
                ExpensesModel.amount_tax_inc.name,
            ]
        ].head()
        raise ValueError(
            f'The provided tax_exc and tax_inc amounts are not consistent '
            f'with the provided vat_amount; for example: {examples}'
        )
