""" Script to calculate the vehicle table on which to compute impacts."""
import logging
import os
import typing

import numpy as np
import pandas as pd
import sqlalchemy as sa

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import (BusinessUnitsModel, CollaboratorsModel,
                                     SoonGoRecordsModel)
from soongo_data.sql_mappings import (CollaboratorsTable)
from soongo_data.utils.adress import parse_df_adress
from soongo_data.utils.bu import get_business_units
from soongo_data.utils.fetch import get_org_param
from soongo_data.utils.input_tables import (InputColumn, InputTable,
                                            add_input_table,
                                            add_synchronization_id,
                                            fetch_organization_params,
                                            gen_soongo_emp_id,
                                            regroup_dataframe)
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.type import series_is_nan, str_is_nan


@add_input_table
class EmployeesInputTable(InputTable):

    def __init__(self: typing.Self):
        super().__init__(
            sql_mapping=CollaboratorsTable,
            columns=[
                InputColumn.from_data_column(
                    column=CollaboratorsModel.soongo_collab_reference,
                    unique=True,
                    nullable=False,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.organization_collaborator_id,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.firstname,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.lastname,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.role,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.work_location,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.organization_collaborator_category,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.employee_entry_date,
                    sql_name='date_from',
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.employee_exit_date,
                    sql_name='date_to',
                ),
                InputColumn.from_data_column(
                    column=BusinessUnitsModel.business_unit,
                    format=r'\w+(?: > \w+)*',
                ),
                InputColumn.from_data_column(
                    column=BusinessUnitsModel.geography,
                    format=r'\w+(?: > \w+)*',
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.alternative_names,
                    nullable=False,
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
                    column=CollaboratorsModel.email,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.manager_soongo_reference,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.picture_href,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.personal_phone_number,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.professional_phone_number,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.civility,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.personal_address,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.birthplace,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.birthdate,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.license_number,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.license_country,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.license_issuing_place,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.license_issuing_date,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.personal_street_number,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.personal_street_name,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.personal_postal_code,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.personal_city,
                ),
                InputColumn.from_data_column(
                    column=CollaboratorsModel.personal_country,
                ),
                InputColumn.from_data_column(
                    column=BusinessUnitsModel.analytical_entity_1,
                    sql_name='analytical_entity',
                ),
            ]
        )

    def _get_df(
        self: typing.Self,
        connector_data: ConnectorData,
        logger: logging.Logger,
        fetch_params_dict: typing.Optional[dict] = None,
    ) -> pd.DataFrame:
        """ Get Employees tables

        :param gac_data: Gac Data Class with all folders
        :param havas_data: Havas Data Class with all folders
        """
        org_employees_params = fetch_organization_params(
            connector_data.organization_name
        )[self.name]
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

        # Get Soongo_collab_reference for employees
        full_names = (
            combined_df[CollaboratorsModel.employee_full_name.name]
            if CollaboratorsModel.employee_full_name.name in combined_df.columns
            else None
        )
        first_names = (
            combined_df[CollaboratorsModel.firstname.name]
            if CollaboratorsModel.firstname.name in combined_df.columns
            else None
        )
        last_names = (
            combined_df[CollaboratorsModel.lastname.name]
            if CollaboratorsModel.lastname.name in combined_df.columns
            else None
        )
        combined_df[CollaboratorsModel.soongo_collab_reference.name] = gen_soongo_emp_id(
            full_name_series=full_names,
            firstname_series=first_names,
            lastname_series=last_names,
            df_index=combined_df.index,
            organization_name=connector_data.organization_name,
        )
        combined_df[CollaboratorsModel.alternative_names.name] = (
            combined_df[CollaboratorsModel.soongo_collab_reference.name]
        )

        # Regroup based on id
        org_id_col = get_org_param(
            organization_name=connector_data.organization_name,
            param_name='collaborator_unique_id',
        )
        combined_df = regroup_dataframe(
            raw_df=combined_df,
            groupby_col=org_id_col,
            logger=logger,
        ).reset_index(drop=True)

        combined_df = self.deduplicate(
            combined_df=combined_df,
            logger=logger,
            id_col=org_id_col,
        )
        combined_df = self.match_managers(
            combined_df=combined_df,
            organization_name=connector_data.organization_name,
        )
        if org_employees_params.get('infer_category'):
            combined_df = infer_category(combined_df)

        # Parse address
        if CollaboratorsModel.personal_address.name in combined_df.columns:
            combined_df = parse_df_adress(combined_df)

        return self.final_format(combined_df)

    @classmethod
    def deduplicate(
        cls: typing.Self,
        combined_df: pd.DataFrame,
        logger: logging.Logger,
        id_col: str,
    ) -> pd.DataFrame:
        """ Deduplicate DataFrame

        :param combined_df: pandas DataFrame of employee names and ids
        :param logger: logger
        """
        # Drop missing ids
        missing_name_sets = str_is_nan(
            combined_df[CollaboratorsModel.soongo_collab_reference.name]
        )
        combined_df = combined_df.loc[
            ~missing_name_sets,
        ]
        logger.info(
            'Dropped %d missing name set ids',
            missing_name_sets.sum(),
        )

        # Name set deduplication rule
        combined_df = cls.rebuild_from_id(
            dup_df=combined_df,
            id_col=CollaboratorsModel.soongo_collab_reference.name,
            logger=logger,
        )

        # Employee matriculation deduplication rule
        combined_df = cls.rebuild_from_id(
            dup_df=combined_df,
            id_col=id_col,
            logger=logger,
        )
        combined_df[CollaboratorsModel.alternative_names.name] = (
            combined_df[CollaboratorsModel.alternative_names.name].mask(
                str_is_nan(combined_df[CollaboratorsModel.alternative_names.name]),
                combined_df[CollaboratorsModel.soongo_collab_reference.name]
            )
        )

        return combined_df

    @staticmethod
    def rebuild_from_id(dup_df: pd.DataFrame, id_col: str, logger: logging.Logger):
        """ Rebuild a DataFrame from an id col as a deduplication method

        :param dup_df: duplicated dataframe
        :param id_col: string name of the column to use as id

        :return: deduplicated column id.
        """
        initial_rows = len(dup_df)
        initial_ids = set(dup_df[id_col])
        soongo_id = CollaboratorsModel.soongo_collab_reference.name

        missing_id = str_is_nan(dup_df[id_col])
        if id_col == CollaboratorsModel.email.name:
            missing_id = missing_id | dup_df[id_col].isin(
                [
                    'nc@groupe-acorus.fr',
                    'fabienne.deborde@gif.fr',  # same email used by 12 peeps
                ],
            )
        missing_id_df = dup_df.loc[missing_id,]
        id_df = dup_df.loc[~missing_id]
        dedup_df = id_df[[id_col]].drop_duplicates()
        for var_col in id_df.columns:
            if var_col == id_col:
                continue

            col_df = id_df.loc[
                ~series_is_nan(id_df[var_col]),
                [id_col, var_col]
            ].drop_duplicates(subset=id_col)  # Effectively keeps first entry

            if var_col == soongo_id:  # Record the variations
                alt_names_df = id_df.groupby(
                    id_col
                )[soongo_id].agg(', '.join).reset_index()
                alt_names_df.rename(
                    columns={soongo_id: 'temp_alt_names'},
                    inplace=True,
                )
                col_df = col_df.merge(
                    right=alt_names_df,
                    on=id_col,
                    validate='1:1',
                    indicator=True,
                )
                assert (col_df._merge == 'both').all()
                col_df.drop(columns='_merge', inplace=True)

            dedup_df = dedup_df.merge(
                right=col_df,
                how='left',
                on=id_col,
                validate='1:1',
            )

        dedup_df = pd.concat([missing_id_df, dedup_df], axis=0)

        if 'temp_alt_names' in dedup_df.columns:
            augmented_alt_names = np.where(
                str_is_nan(dedup_df[CollaboratorsModel.alternative_names.name]),
                dedup_df['temp_alt_names'],
                dedup_df[CollaboratorsModel.alternative_names.name] + ', ' +
                dedup_df['temp_alt_names']
            )
            dedup_df[CollaboratorsModel.alternative_names.name] = np.where(
                ~str_is_nan(dedup_df['temp_alt_names']),
                augmented_alt_names,
                dedup_df[CollaboratorsModel.alternative_names.name]
            )
            dedup_df.drop('temp_alt_names', axis=1, inplace=True)

            # Deduplication alternative names
            dedup_df[CollaboratorsModel.alternative_names.name] = (
                dedup_df[CollaboratorsModel.alternative_names.name].str.split(
                    ', '
                ).apply(set).apply(lambda x: ', '.join(x))
            )
        assert set(dedup_df[id_col]) == initial_ids
        assert (dedup_df.columns == dup_df.columns).all()
        logger.info(
            'Deduplicated %d employee rows using column %s',
            initial_rows - len(dedup_df),
            id_col,
        )
        return dedup_df

    def match_managers(
        self: typing.Self,
        combined_df: pd.DataFrame,
        organization_name: str
    ) -> pd.DataFrame:
        """Ensure that managers soongo_collab_reference is aligned with their
        reference as employees.
        """
        if (
            (CollaboratorsModel.organization_collaborator_id.name in combined_df.columns)
            and (CollaboratorsModel.manager_organization_id.name in combined_df.columns)
        ):
            collab_df = combined_df.loc[
                ~str_is_nan(
                    combined_df[CollaboratorsModel.organization_collaborator_id.name]
                ),
                [
                    CollaboratorsModel.organization_collaborator_id.name,
                    CollaboratorsModel.soongo_collab_reference.name,
                ]
            ].rename(
                {
                    CollaboratorsModel.soongo_collab_reference.name: CollaboratorsModel.manager_soongo_reference.name,
                    CollaboratorsModel.organization_collaborator_id.name: CollaboratorsModel.manager_organization_id.name,
                },
                axis=1,
            ).drop_duplicates()
            combined_df = combined_df.merge(
                collab_df,
                on=CollaboratorsModel.manager_organization_id.name,
                how='left',
                validate='m:1',
            )
        else:
            combined_df[CollaboratorsModel.manager_soongo_reference.name] = ''

        manager_first_names = (
            combined_df[CollaboratorsModel.manager_first_name.name]
            if CollaboratorsModel.manager_first_name.name in combined_df.columns
            else None
        )
        manager_last_names = (
            combined_df[CollaboratorsModel.manager_last_name.name]
            if CollaboratorsModel.manager_last_name.name in combined_df.columns
            else None
        )
        manager_full_names = (
            combined_df[CollaboratorsModel.manager_full_name.name]
            if CollaboratorsModel.manager_full_name.name in combined_df.columns
            else None
        )
        combined_df[CollaboratorsModel.manager_soongo_reference.name] = (
            combined_df[CollaboratorsModel.manager_soongo_reference.name].mask(
                str_is_nan(
                    combined_df[CollaboratorsModel.manager_soongo_reference.name]
                ),
                gen_soongo_emp_id(
                    full_name_series=manager_full_names,
                    firstname_series=manager_first_names,
                    lastname_series=manager_last_names,
                    df_index=combined_df.index,
                    organization_name=organization_name,
                )
            )
        )

        return combined_df

    def final_format(
        self: typing.Self,
        combined_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Final formatting of the employee table"""
        assert combined_df[CollaboratorsModel.soongo_collab_reference.name].is_unique
        combined_df = self.fill_missing_cols(
            df=combined_df,
        )

        for col in self.columns:
            if pd.api.types.is_string_dtype(col.dtype):
                combined_df[col.name] = (
                    combined_df[col.name].str.replace(
                        r'^nan$', '', regex=True, case=False,
                    ).fillna('')
                )

        return combined_df[self.return_column_names()]

    def to_sql(
        self: typing.Self,
        data_df: pd.DataFrame,
        organization_id: str,
        session: sa.orm.Session,
        logger: logging.Logger,
        update_values: str = 'null_only',
        columns: typing.Optional[typing.List[str]] = None,
    ) -> None:

        super().to_sql(
            data_df,
            organization_id,
            session,
            logger,
            update_values,
            columns,
        )

        session.execute(
            sa.text('refresh materialized view publ.collaborators_view;')
        )


def infer_category(
    role_df: pd.DataFrame,
) -> pd.DataFrame:
    """ Infer collaborator category from their role.

    :param role_df: pd DataFrame which must have an
        organization_collaborator column and a role column*

    :raises ValueError: if necessary cols are not available
    """
    if not (
        {
            CollaboratorsModel.role.name,
            CollaboratorsModel.organization_collaborator_category.name,
        }.issubset(role_df.columns)
    ):
        # Nothing to infer
        return role_df

    if (
        series_is_nan(
            role_df[CollaboratorsModel.organization_collaborator_category.name]
        ) == series_is_nan(
            role_df[CollaboratorsModel.role.name]
        )
    ).all():
        # Nothing to infer
        return role_df

    # Strategy 1: fill internal_category with that of collab with same role
    available_orga = role_df.loc[
        ~series_is_nan(
            role_df[CollaboratorsModel.organization_collaborator_category.name]
        ) & ~series_is_nan(
            role_df[CollaboratorsModel.role.name]
        ),
        [
            CollaboratorsModel.organization_collaborator_category.name,
            CollaboratorsModel.role.name,
        ],
    ]

    available_orga['alt_cat'] = available_orga.groupby(
        CollaboratorsModel.role.name
    )[CollaboratorsModel.organization_collaborator_category.name].transform(
        lambda x: x.mode()[0]  # Mode returns a series even if one mode
    )
    available_orga = available_orga[
        [
            CollaboratorsModel.role.name,
            'alt_cat',
        ]
    ].drop_duplicates()

    role_df = role_df.merge(
        available_orga,
        on=[CollaboratorsModel.role.name],
        validate='m:1',
        how='left',
        indicator='_role_merge',
    )
    assert (role_df.loc[
        ~series_is_nan(
            role_df[CollaboratorsModel.organization_collaborator_category.name]
        ) & ~series_is_nan(
            role_df[CollaboratorsModel.role.name]
        ),
        '_role_merge',
    ] == 'both').all()

    # Strategy 2: fill in when part of the role title matches (e.g. director)
    role_df['role_indicator'] = ''
    i = 0
    for role_pattern in (
        r'charg(?:é|e)',
        r'responsable',
        r'direct(?:eur|rice) g(?:é|e)n(?:é|e)ral',
        r'(?!.*g(?:é|e)n(?:é|e)ral.*).*direct(?:eur|rice).*',
    ):
        indicator = role_df[CollaboratorsModel.role.name].str.match(
            pat=role_pattern, case=False,
        ).fillna(False)
        # Check no overlap across series
        assert series_is_nan(
            role_df.loc[indicator, 'role_indicator']
        ).all()
        role_df['role_indicator'] = (
            role_df['role_indicator'].mask(
                indicator,
                i,
            )
        )
        assert str_is_nan(
            role_df.loc[
                str_is_nan(role_df[CollaboratorsModel.role.name]),
                'role_indicator',
            ]
        ).all()
        i += 1
    role_df['role_indicator'] = role_df['role_indicator'].mask(
        series_is_nan(role_df[CollaboratorsModel.role.name]),
        '',
    )
    available_indicator = role_df.loc[
        ~series_is_nan(
            role_df[CollaboratorsModel.organization_collaborator_category.name]
        ) & ~series_is_nan(
            role_df['role_indicator']
        ),
        [
            CollaboratorsModel.organization_collaborator_category.name,
            'role_indicator',
        ],
    ]
    available_indicator['alt_cat2'] = available_indicator.groupby(
        'role_indicator'
    )[CollaboratorsModel.organization_collaborator_category.name].transform(
        lambda x: x.mode()[0]  # Mode returns a series even if one mode
    )
    available_indicator = available_indicator[
        [
            'role_indicator',
            'alt_cat2',
        ]
    ].drop_duplicates()

    role_df = role_df.merge(
        available_indicator,
        on=['role_indicator'],
        validate='m:1',
        how='left',
        indicator='_indicator_merge',
    )
    for substitute_col in ['alt_cat', 'alt_cat2']:
        role_df[CollaboratorsModel.organization_collaborator_category.name] = (
            role_df[CollaboratorsModel.organization_collaborator_category.name].mask(
                series_is_nan(
                    role_df[CollaboratorsModel.organization_collaborator_category.name]
                ),
                role_df[substitute_col]
            )
        )

    role_df.drop(
        ['alt_cat', 'alt_cat2', '_role_merge', '_indicator_merge'],
        axis=1,
        inplace=True,
    )
    return role_df


if __name__ == "__main__":

    logger = gen_logger('employees_table')
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
    employee_table = EmployeesInputTable()
    employee_df = employee_table.get(
        connector_data=connector_data,
        logger=logger,
    )
    employee_table.check_columns(
        data_df=employee_df,
        logger=logger,
    )
    employee_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{employee_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
