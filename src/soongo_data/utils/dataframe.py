import typing

import pandas as pd


def merge_overlapping_rows(
    df: pd.DataFrame,
    id_cols: typing.List[str],
    start_col: str,
    end_col: str,
    null_is_infinity: bool = True,
) -> pd.DataFrame:
    """
    Merge rows in a DataFrame that are contiguous or overlapping for the same
    id columns.

    :param df: Input DataFrame
    :param id_cols: List of columns to identify unique entities
    :param start_col: Name of the start date column (date_from)
    :param end_col: Name of the end date column (date_to)
    :return: DataFrame with merged rows
    """
    if null_is_infinity:
        df[start_col] = df[start_col].fillna(pd.Timestamp.max)
        df[end_col] = df[end_col].fillna(pd.Timestamp.max)

    df = df.sort_values(by=id_cols + [start_col])

    grouped_df = df.groupby(id_cols, group_keys=False)
    group_count = grouped_df.ngroups

    def merge_group(group):
        # Initialize a stack to store merged intervals
        merged = []
        for _, row in group.iterrows():
            if not merged or row[start_col] > merged[-1][end_col]:
                # No overlap, add a new interval
                merged.append(row)
            else:
                # Overlap, merge intervals
                merged[-1][start_col] = min(merged[-1][start_col], row[start_col])
                merged[-1][end_col] = max(merged[-1][end_col], row[end_col])
        return pd.DataFrame(merged)

    merged_df = grouped_df.apply(merge_group)
    merged_df = merged_df.drop_duplicates(
        subset=id_cols + [start_col, end_col]
    )

    if null_is_infinity:
        for date_col in [start_col, end_col]:
            merged_df[date_col] = merged_df[date_col].replace(
                pd.Timestamp.max, pd.NaT
            )

    if group_count != merged_df.groupby(id_cols).ngroups:
        raise ValueError(
            'Merging contiguous/overlapping rows failed, '
            'number of groups changed'
        )

    return merged_df
