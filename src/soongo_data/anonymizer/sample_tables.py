""" Sampler - generate synthetic data from actual tables
"""
import argparse
import logging
import os
import random
import typing
import uuid

import numpy as np
import pandas as pd
import sqlalchemy as sa
import yaml

from soongo_data.data_models import (
    CollaboratorsModel, EquipmentsModel, ExpensesModel, VehiclesModel,
    ClaimsModel, AccidentsModel, BusinessUnitsModel
)
from soongo_data.sql_mappings import (
    CollaboratorsTable,
    VehiclesTable,
    EquipmentTable,
    VehicleAttributionsTable,
    MileagesTable,
    ExpensesTable,
    AccidentsTable,
    TaxesTable,
    RentalCarsTable,
    TrainsPlanesTable,
    HotelsTable,
    ExpenseClaimsTable,
    VehicleContractsTable,
    OrganizationsTable,
    ConnectorsTable,
    SynchronisationsTable,
    VehicleModelsTable,
    VehicleBrandsTable
)
from soongo_data.utils.db import gen_session
from soongo_data.utils.enums import (
    FiscalType, InsurancePremiums, RentCategory, FuelTypes, ExpenseType,
    SynchronizationTypes
)
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.type import (
    str_is_nan, series_is_nan, df_is_nan
)
from soongo_data.utils.uploads import (
    BusinessUnitInserter, SynchronisationInserter, prepare_row_dict
)


class Sampler:
    TABLE_DICT = {
        CollaboratorsTable.__tablename__: CollaboratorsTable,
        VehiclesTable.__tablename__: VehiclesTable,
        EquipmentTable.__tablename__: EquipmentTable,
        VehicleContractsTable.__tablename__: VehicleContractsTable,
        VehicleAttributionsTable.__tablename__: VehicleAttributionsTable,
        MileagesTable.__tablename__: MileagesTable,
        ExpensesTable.__tablename__: ExpensesTable,
        AccidentsTable.__tablename__: AccidentsTable,
        TaxesTable.__tablename__: TaxesTable,
        RentalCarsTable.__tablename__: RentalCarsTable,
        TrainsPlanesTable.__tablename__: TrainsPlanesTable,
        HotelsTable.__tablename__: HotelsTable,
        ExpenseClaimsTable.__tablename__: ExpenseClaimsTable,
    }
    ANON_PLATE_COL = 'anon_plate_number'
    ANON_EMPLOYEE_COL = 'anon_employee_col'
    LETTERS = tuple('azertyuiopqsdfghjklmwxcvbn')
    NUMBERS = tuple('0123456789')
    UNIQUE_CONSTRAINTS = {
        ExpensesTable.__tablename__: [
            ExpensesModel.expense_reference.name,
        ],
        AccidentsTable.__tablename__: [
            AccidentsModel.accident_ref.name,
        ],
        CollaboratorsTable.__tablename__: [
            CollaboratorsModel.organization_collaborator_id.name
        ],
        EquipmentTable.__tablename__: [
            EquipmentsModel.equipment_reference.name,
        ],
    }

    def __init__(
        self,
        logger: logging.Logger,
        sql_session: sa.orm.Session,
        target_organization_slug: str,
        source_organizations: typing.List[str],
        name_lexicon: str,
        config: dict,
        seed: int = 13,
    ):
        """ Selects plates to sample to generate additional cars

        :param config_path: str path to the sampling config
        :param input_tables: InputTable object with all data
        """
        self.sample_params = config
        self.sql_session = sql_session
        self.plate_lst = sql_session.execute(
            sa.select(
                VehiclesTable.plate_number
            ).distinct()
        ).scalars().all()
        self.employee_lst = sql_session.execute(
            sa.select(
                CollaboratorsTable.soongo_collab_reference
            ).distinct()
        ).scalars().all()
        self.logger = logger
        self.sampled_vehicles = []
        self.sampled_collaborators = []
        self.seed = seed
        self.source_organizations = source_organizations
        self.target_organization_slug = target_organization_slug
        self.target_organization_id = sql_session.execute(
            sa.select(
                OrganizationsTable.id
            ).where(
                OrganizationsTable.slug == target_organization_slug,
            )
        ).scalar()
        self.synchronization_id = SynchronisationInserter(
            session=sql_session,
            organization_id=self.target_organization_id,
        )._insert_row(
            synchronisation_id=str(uuid.uuid4()),
            connector_id=sql_session.execute(
                sa.select(
                    ConnectorsTable.id
                ).where(
                    ConnectorsTable.name == 'WEBAPP',
                )
            ).scalar(),
            synchronisation_type=SynchronizationTypes.manual.value,
        )
        self.sql_session.commit()
        self.name_lexicon = self.extract_name_set(name_lexicon)
        self.choice_set = self.gen_choice_set()
        self.sampled_associations = self.pick_associations()

    def push_anon_data_to_sql(
        self: typing.Self,
        chunksize: int = 10**5
    ) -> None:
        """ Push anonymized data to SQL tables
        """
        try:
            for table_name, input_table in self.TABLE_DICT.items():
                self.logger.info(
                    'Sampling and anonymizing table %s',
                    table_name,
                )
                anon_table = self.sample_table(input_table)
                self.logger.info(
                    (
                        'Sampled %d rows. Pushing to database in batches of %d '
                        'using synchronisation_id %s'
                    ),
                    anon_table.shape[0],
                    chunksize,
                    self.synchronization_id,
                )
                anon_table.to_sql(
                    name=table_name,
                    con=self.sql_session.bind,
                    index=False,
                    chunksize=chunksize,
                    if_exists='append',
                    schema='publ',
                )
        except Exception as error:
            self.logger.error(
                (
                    'Error while sampling and anonymizing table %s: %s.'
                    ' Rolling back and deleting synchronisation_id %s'
                ),
                table_name,
                error,
                self.synchronization_id,
            )
            session.execute(
                sa.delete(SynchronisationsTable).where(
                    SynchronisationsTable.id == self.synchronization_id,
                )
            )
        else:
            self.logger.info(
                'Successfully sampled and anonymized all tables for organization %s',
                self.target_organization_slug,
            )
        finally:
            session.commit()
            # We commit even when an error occurs to ensure that
            # the synchronisation_id is deleted from the database
            # by cascading this will delete all uploaded data

    def pick_associations(self) -> pd.DataFrame:
        """ Pick the collaborators vehicles association which will be used
        in the sampling based on the conditions in the sampling params. This
        is the base to fetch data from all other tables; if collaborator/plate
        matches the association, then the data is fetched, else it isn't.

        Same association may be sampled multiple times in which case the data
        is duplicated. All names and plate numbers are anonymized which also
        ensures their unicity in the final synthetic data.

        :returns: None but place each of the sampled_associations for each of
            the sample in the sampling dict in the attribute
            self.sampled_associations
        """
        self.logger.info(
            'Sampling associations for organization %s and samping_params %s',
            self.target_organization_slug,
            self.sample_params,
        )
        eligible_vehicles = self.return_eligible_vehicle_ids(
            condition_lst=self.sample_params.get('conditions', [])
        )

        eligible_associations = pd.read_sql(
            sql=sa.select(
                VehicleAttributionsTable.vehicle_id,
                VehiclesTable.plate_number,
                VehicleAttributionsTable.collaborator_id,
                CollaboratorsTable.soongo_collab_reference,
            ).select_from(
                VehicleAttributionsTable
            ).join(
                VehiclesTable,
                VehiclesTable.id == VehicleAttributionsTable.vehicle_id,
            ).outerjoin(
                CollaboratorsTable,
                CollaboratorsTable.id == VehicleAttributionsTable.collaborator_id,
            ).where(
                VehicleAttributionsTable.vehicle_id.in_(eligible_vehicles),
            ).distinct(),
            con=self.sql_session.bind,
        )

        sampled_vehicle_ids = random.choices(
            eligible_vehicles,
            k=self.sample_params['nb_sampling'],
        )
        # Add duplicates for each sampled vehicle_id
        sampled_associations = pd.concat(
            [
                eligible_associations[eligible_associations['vehicle_id'] == vid]
                for vid in sampled_vehicle_ids
            ],
            ignore_index=True,
        )
        self.sampled_vehicles = sampled_associations['vehicle_id'].unique().tolist()
        self.sampled_collaborators = sampled_associations['collaborator_id'].unique().tolist()

        sampled_associations[self.ANON_PLATE_COL] = self.anonymize_plates(
            sampled_associations[VehiclesModel.plate_number.name]
        )
        # Same plate number may exist across multiple organizations
        # ensure that we obtain the unique plate numbers to not insert the
        # same plate number multiple times in the demo organization
        sampled_associations = sampled_associations.drop_duplicates(
            subset=[self.ANON_PLATE_COL],
        )
        sampled_associations[self.ANON_EMPLOYEE_COL] = self.anonymize_name(
            sampled_associations[CollaboratorsModel.soongo_collab_reference.name]
        )

        # Same soongo_collab_reference may exist across multiple 
        # organizations. Ensure that we obtain a unique reference
        # same collab_reference multiple times in the demo organization
        sampled_associations = sampled_associations.drop_duplicates(
            subset=[self.ANON_EMPLOYEE_COL],
        )

        return sampled_associations[
            [
                VehiclesModel.vehicle_id.name,
                self.ANON_PLATE_COL,
                CollaboratorsModel.collaborator_id.name,
                self.ANON_EMPLOYEE_COL,
            ]
        ]

    def sample_table(
        self,
        sql_table: sa.Table,
    ) -> pd.DataFrame:
        """ Over sample table.

        Three scenarios:
            both plate and employee id available, merge using both m:m,
            substitute plate_col and employee id by anon version

            plate_col only available, merge using plate_col only m:m

            employee only available, merge using employee_id only m:m

        :param table_df: input table to over sample and anonymize
        """
        table_df = self.fetch_table_df(sql_table)
        table_cols = table_df.columns.tolist()

        if sql_table.__tablename__ == VehiclesTable.__tablename__:
            sampling_cols = [VehiclesModel.vehicle_id.name]
            table_df['vehicle_id'] = table_df['id']

        elif sql_table.__tablename__ == CollaboratorsTable.__tablename__:
            sampling_cols = [CollaboratorsModel.collaborator_id.name]
            table_df['collaborator_id'] = table_df['id']

        else:
            sampling_cols = []
            if VehiclesModel.vehicle_id.name in table_cols:
                sampling_cols.append(VehiclesModel.vehicle_id.name)
            if CollaboratorsModel.collaborator_id.name in table_cols:
                sampling_cols.append(CollaboratorsModel.collaborator_id.name)

        mask = pd.Series(False, table_df.index)
        for col in sampling_cols:
            mask = mask | ~str_is_nan(table_df[col])
        available_df = table_df[mask].copy()

        if len(sampling_cols) == 1:
            oversampled_df = available_df.merge(
                right=self.sampled_associations,
                on=sampling_cols[0],
                how='inner',  # Selection
            )
        elif len(sampling_cols) == 2:
            vehicle_available_sampled = available_df[
                ~series_is_nan(available_df[VehiclesModel.vehicle_id.name])
            ]
            vehicle_sample = self.sampled_associations[
                [
                    VehiclesModel.vehicle_id.name,
                    self.ANON_EMPLOYEE_COL,
                    self.ANON_PLATE_COL,
                ]
            ]
            vehicle_available_sampled = vehicle_available_sampled.merge(
                right=vehicle_sample,
                on=VehiclesModel.vehicle_id.name,
                how='inner',  # Selection
            )
            collaborator_available_sampled = available_df[
                ~series_is_nan(available_df[CollaboratorsModel.collaborator_id.name])
                &
                series_is_nan(available_df[VehiclesModel.vehicle_id.name])
            ]
            collaborator_sample = self.sampled_associations[
                [
                    CollaboratorsModel.collaborator_id.name,
                    self.ANON_EMPLOYEE_COL,
                    self.ANON_PLATE_COL,
                ]
            ]
            collaborator_available_sampled = collaborator_available_sampled.merge(
                right=collaborator_sample,
                on=CollaboratorsModel.collaborator_id.name,
                how='inner',  # Selection
            )
            oversampled_df = pd.concat(
                [
                    vehicle_available_sampled,
                    collaborator_available_sampled,
                ],
                ignore_index=True,
            )
        else:
            raise ValueError(
                'No plate or employee id available in table '
                f'{table_df}. Cannot sample.'
            )
        for change in self.sample_params.get('changes', []):
            oversampled_df = self.apply_change(
                df=oversampled_df,
                change_dict=change,
                table_name=sql_table.__tablename__,
            )

        unique_constraints = self.UNIQUE_CONSTRAINTS.get(
            sql_table.__tablename__,
            []
        )
        for constraint in unique_constraints:
            oversampled_df[constraint] = oversampled_df[constraint].apply(
                lambda x: str(uuid.uuid4())
            )

        oversampled_df = self.anonymize_table(
            table_df=oversampled_df,
            sql_table=sql_table,
        )

        if sql_table.__tablename__ == VehicleAttributionsTable.__tablename__:
            missing_both_collab_and_bu = df_is_nan(
                oversampled_df[
                    [
                        BusinessUnitsModel.business_unit_id.name,
                        CollaboratorsModel.collaborator_id.name,
                    ]
                ]
            ).all(axis=1)
            if missing_both_collab_and_bu.sum() > 0:
                # If both business unit and collaborator are NaN, drop the row
                # as it does not make sense to have a vehicle attribution without
                # either a business unit or a collaborator.
                self.logger.error(
                    'Dropping %d rows with both business unit and collaborator NaN out of %d rows',
                    missing_both_collab_and_bu.sum(),
                    oversampled_df.shape[0],
                )
                oversampled_df = oversampled_df[
                    ~df_is_nan(
                        oversampled_df[
                            [
                                BusinessUnitsModel.business_unit_id.name,
                                CollaboratorsModel.collaborator_id.name,
                            ]
                        ]
                    ).all(axis=1)
                ]

        sql_cols = [col for col in table_cols if col != 'id']
        return oversampled_df[sql_cols]

    def fetch_table_df(
        self: typing.Self,
        sql_table: sa.Table,
    ) -> pd.DataFrame:
        where_conds = []
        is_vehicle = sql_table.__tablename__ == VehiclesTable.__tablename__
        is_collab = sql_table.__tablename__ == CollaboratorsTable.__tablename__
        has_vehicle = hasattr(sql_table, VehiclesModel.vehicle_id.name)
        has_collab = hasattr(sql_table, CollaboratorsModel.collaborator_id.name)

        if is_vehicle:
            where_conds.append(
                sql_table.id.in_(self.sampled_vehicles)
            )
        elif is_collab:
            where_conds.append(
                sql_table.id.in_(self.sampled_collaborators)
            )
        elif has_vehicle and has_collab:
            where_conds.append(
                sa.or_(
                    sql_table.vehicle_id.in_(self.sampled_vehicles),
                    sa.and_(
                        sql_table.vehicle_id.is_(None),
                        sql_table.collaborator_id.in_(self.sampled_collaborators),
                    )
                )
            )
        elif has_vehicle:
            where_conds.append(
                sql_table.vehicle_id.in_(self.sampled_vehicles)
            )
        elif has_collab:
            where_conds.append(
                sql_table.collaborator_id.in_(self.sampled_collaborators)
            )

        query = sa.select(sql_table).where(*where_conds)

        return pd.read_sql(
            sql=query,
            con=self.sql_session.bind,
        )

    def anonymize_table(
        self: typing.Self,
        table_df: pd.DataFrame,
        sql_table: sa.Table,
    ) -> pd.DataFrame:
        """ Anonymize table_df by anonymizing names and plate numbers

        :param table_df: DataFrame with the table to anonymize

        :returns: DataFrame with anonymized names and plate numbers
        """
        table_df = self.replace_names(table_df)

        if hasattr(sql_table, VehiclesModel.plate_number.name):
            table_df[VehiclesModel.plate_number.name] = (
                table_df[self.ANON_PLATE_COL]
            )

        if hasattr(sql_table, CollaboratorsModel.soongo_collab_reference.name):
            table_df[CollaboratorsModel.soongo_collab_reference.name] = (
                table_df[self.ANON_EMPLOYEE_COL]
            )

        if hasattr(sql_table, VehiclesModel.vehicle_id.name):
            table_df[VehiclesModel.vehicle_id.name] = (
                self.fetch_new_vehicle_ids(
                    table_df[self.ANON_PLATE_COL]
                )
            )

        if hasattr(sql_table, CollaboratorsModel.collaborator_id.name):
            table_df[CollaboratorsModel.collaborator_id.name] = (
                self.fetch_new_collaborator_ids(
                    table_df[self.ANON_EMPLOYEE_COL]
                )
            )

        if hasattr(sql_table, EquipmentsModel.equipment_reference.name) and sql_table.__tablename__ != EquipmentTable.__tablename__:
            table_df[EquipmentsModel.equipment_id.name] = (
                self.fetch_new_equipment_ids(
                    table_df[EquipmentsModel.equipment_reference.name]
                )
            )

        if hasattr(sql_table, 'organization_id'):
            table_df['organization_id'] = (
                self.target_organization_id
            )
        if hasattr(sql_table, 'synchronisation_id'):
            table_df['synchronisation_id'] = (
                self.synchronization_id
            )

        return table_df

    def fetch_new_collaborator_ids(
        self: typing.Self,
        anon_name_col: pd.Series,
    ) -> pd.Series:
        names_to_id = self.sql_session.execute(
            sa.select(CollaboratorsTable.soongo_collab_reference, CollaboratorsTable.id).where(
                CollaboratorsTable.soongo_collab_reference.in_(
                    anon_name_col[~str_is_nan(anon_name_col)].unique()
                )
            )
        ).fetchall()
        names_to_id = dict(names_to_id)

        new_collaborator_ids = anon_name_col.map(
            names_to_id
        )
        if (new_collaborator_ids.notna() != anon_name_col.notna()).any():
            raise ValueError(
                'The new collaborators must be pushed to database before pushing'
                ' all other tables.'
            )

        return new_collaborator_ids

    def fetch_new_equipment_ids(
        self: typing.Self,
        anon_equipment_col: pd.Series,
    ) -> pd.Series:
        equipment_to_id = self.sql_session.execute(
            sa.select(EquipmentTable.equipment_reference, EquipmentTable.id).where(
                EquipmentTable.equipment_reference.in_(
                    anon_equipment_col[~str_is_nan(anon_equipment_col)].unique()
                ),
                EquipmentTable.organization_id == self.target_organization_id,
            )
        ).fetchall()
        equipment_to_id = dict(equipment_to_id)
        new_equipment_ids = anon_equipment_col.map(
            equipment_to_id
        )
        if (new_equipment_ids.notna() != anon_equipment_col.notna()).any():
            raise ValueError(
                'The new equipments must be pushed to database before pushing'
                ' all other tables.'
            )
        return new_equipment_ids

    def insert_table(
        self: typing.Self,
        table_df: pd.DataFrame,
        sql_table: sa.Table,
        chunksize: int = 10**5,
    ) -> None:
        """ Insert table_df into sql_table
        :param table_df: DataFrame with the table to insert
        :param sql_table: SQLAlchemy Table object to insert into
        :param chunksize: int number of rows to insert at once
        """
        new_rows_dict = [
            prepare_row_dict(
                row_dict=row_dict,
                organization_id=self.target_organization_id,
                json_columns=[],
                sql_mapping_columns=[column.name for column in sql_table.columns],
                drop_id=True,
            )
            for row_dict in table_df.to_dict(orient='records')
        ]
        logger.info(
            'Rows prepared, starting insertion into table %s',
            sql_table.__tablename__,
        )

        insert_count = 0
        next_limit = min(chunksize, len(new_rows_dict))
        while insert_count < len(new_rows_dict):

            rows = new_rows_dict[insert_count:next_limit]
            sql_statement = sa.insert(sql_table).values(
                rows
            )
            session.execute(sql_statement)
            session.flush()

    def fetch_new_vehicle_ids(
        self: typing.Self,
        anon_plate_col: pd.Series,
    ) -> pd.Series:
        plates_to_id = self.sql_session.execute(
            sa.select(VehiclesTable.plate_number, VehiclesTable.id).where(
                VehiclesTable.plate_number.in_(
                    anon_plate_col[~str_is_nan(anon_plate_col)].unique()
                )
            )
        ).fetchall()
        plates_to_id = dict(plates_to_id)

        new_plate_ids = anon_plate_col.map(
            plates_to_id
        )
        if (new_plate_ids.notna() != anon_plate_col.notna()).any():
            raise ValueError(
                'The new vehicles must be pushed to database before pushing'
                ' all other tables.'
            )
        return new_plate_ids

    def anonymize_name(
        self: typing.Self,
        name_col: pd.Series,
    ) -> pd.Series:
        """ Anonymize names using a lexicon, updating substitution dict to
        record substitutions

        :param name_col: Series of individual names
        :param name_lexicon: list of names to substitute with
        :param substitution_dict: dictionary of names to substitute

        :returns: new series with anonymized names, and updates substitution
        """
        anon_name_col = name_col
        while anon_name_col.isin(self.employee_lst).any():
            # Identify unique names in name_col
            name_df = name_col.str.split(expand=True)

            # Update names
            new_name_df = name_df.map(
                lambda x: random.choice(self.name_lexicon)
            ).fillna('')
            for col in new_name_df.columns:
                new_name_df[col] = new_name_df[col].str.strip()

            anon_name_col = anon_name_col.mask(
                anon_name_col.isin(self.employee_lst),
                new_name_df.agg(' '.join, axis=1).str.strip()
            )

        self.employee_lst += anon_name_col.tolist()
        return anon_name_col

    def anonymize_plates(
        self: typing.Self,
        plate_col: pd.Series,
    ) -> pd.Series:
        anon_plate_col = plate_col.apply(self.anonymize_individual_plate)
        self.plate_lst += anon_plate_col.tolist()

        return anon_plate_col

    def anonymize_individual_plate(
        self,
        plate_col: str,
    ) -> str:
        """ Individual_plate_anonymizer

        :param plate_col: Series of plate number

        :returns: substituted plate numbers
        """
        anon_plate_col = plate_col
        while anon_plate_col in self.plate_lst:
            anon_plate_col = (
                ''.join(
                    random.choice(self.choice_set[charac])
                    for charac in plate_col.lower()
                )
            )

        return anon_plate_col

    def replace_names(self, sampled_df: pd.DataFrame) -> pd.DataFrame:
        is_name_col = {
            CollaboratorsModel.firstname.name,
            CollaboratorsModel.lastname.name,
            CollaboratorsModel.alternative_names.name,
            CollaboratorsModel.email.name,
            CollaboratorsModel.personal_phone_number.name,
            CollaboratorsModel.professional_phone_number.name,
            CollaboratorsModel.picture_href.name,
        }.intersection(sampled_df.columns)
        if not is_name_col:
            return sampled_df
        elif len(is_name_col) < 3:
            raise ValueError(
                'The table to anonymize has some but not all name columns'
            )

        sampled_df[CollaboratorsModel.alternative_names.name] = (
            sampled_df[self.ANON_EMPLOYEE_COL]
        )
        names_series = sampled_df[self.ANON_EMPLOYEE_COL].str.split(
            expand=False,
        )
        sampled_df[CollaboratorsModel.lastname.name] = (
            names_series.str[0]
        )
        sampled_df[CollaboratorsModel.firstname.name] = (
            names_series.str[1]
        )
        sampled_df[CollaboratorsModel.email.name] = (
            sampled_df[CollaboratorsModel.firstname.name] + '.' + sampled_df[CollaboratorsModel.lastname.name] + '@soongo.co'
        )
        sampled_df[CollaboratorsModel.personal_phone_number.name] = (
            sampled_df[self.ANON_EMPLOYEE_COL].apply(
                lambda x: f'+33{random.randint(6, 7)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}'
            )
        )
        sampled_df[CollaboratorsModel.professional_phone_number.name] = (
            sampled_df[self.ANON_EMPLOYEE_COL].apply(
                lambda x: f'+33{random.randint(6, 7)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}'
            )
        )
        sampled_df[CollaboratorsModel.picture_href.name] = None
        sampled_df[CollaboratorsModel.license_number.name] = (
            sampled_df[self.ANON_EMPLOYEE_COL].apply(
                lambda x: f'{random.randint(10, 99)}AL{random.randint(10000, 99999)}'
            )
        )

        return sampled_df

    def return_eligible_vehicle_ids(self, condition_lst: list) -> list:
        """ Return eligible vehicle_ids

        :param condition_lst: list of conditions
        """
        authorized_tables = {
            table.__tablename__: table for table in
            [
                VehiclesTable,
                VehicleModelsTable,
                VehicleBrandsTable
            ]
        }

        cond_lst = [
            VehiclesTable.organization_id != self.target_organization_id,
            OrganizationsTable.slug.in_(self.source_organizations)
        ]
        for condition in condition_lst:
            if not set(condition['table_name']).issubset(authorized_tables):
                raise ValueError(
                    'Condition table name must be VehiclesTable, Models or Makes.'
                )
            if len(condition['table_name']) > 1:
                raise NotImplementedError(
                    'Multiple table conditions are not supported yet.'
                )
            table_name = condition['table_name'][0]
            condition_table = authorized_tables[table_name]
            if not hasattr(
                condition_table,
                condition['column_name']
            ):
                raise NotImplementedError(
                    f'Condition column {condition["column_name"]} does not '
                    f'exist in table {table_name}'
                )
            sql_col = getattr(
                authorized_tables[table_name],
                condition['column_name'],
            )
            cond_lst.append(
                self.apply_sql_condition(
                    sql_col=sql_col,
                    categorical_values=condition.get('categorical_values'),
                    min_value=condition.get('min_value'),
                    max_value=condition.get('max_value')
                )
            )
        base_query = sa.select(VehiclesTable.id.label('vehicle_id')).select_from(
            VehiclesTable
        ).join(
            OrganizationsTable,
            OrganizationsTable.id == VehiclesTable.organization_id
        ).outerjoin(
            VehicleModelsTable,
            VehicleModelsTable.id == VehiclesTable.model_id,
        ).outerjoin(
            VehicleBrandsTable,
            VehicleBrandsTable.id == VehiclesTable.brand_id,
        )

        eligible_plates = self.sql_session.execute(
            base_query.where(
                *cond_lst
            ).distinct()
        ).scalars().all()

        return eligible_plates

    def apply_change(
        self: typing.Self,
        df: pd.DataFrame,
        change_dict: dict,
        table_name: str,
    ) -> pd.DataFrame:
        change_cols = change_dict['column_names']
        amount_cols = {
            ExpensesModel.amount_tax_inc.name,
            ExpensesModel.amount_tax_exc.name,
        }
        if (
            (VehiclesModel.fiscal_type.name in change_cols)
            and amount_cols.intersection(df.columns)
        ):

            if ExpensesModel.deductible_vat.name in df.columns:
                # Value now wrong, recompute
                df[ExpensesModel.deductible_vat.name] = np.nan
                df[ExpensesModel.net_amount.name] = np.nan

            df = self.infer_vat(df)
            check_df = df[
                (df[VehiclesModel.fiscal_type.name] == FiscalType.utility_car.value)
                &
                pd.notna(df[ExpensesModel.net_amount.name]),
            ]
            assert (check_df[ExpensesModel.net_amount.name] == check_df[ExpensesModel.amount_tax_exc.name]).all()

        if table_name not in change_dict['table_name']:
            return df

        applicability = pd.Series(True, df.index)
        conditions = change_dict.get('conditions', [])
        for condition in conditions:

            applicability &= self.apply_pandas_condition(
                col_series=df[condition['column_name']],
                categorical_values=condition.get('categorical_values'),
                min_value=condition.get('min_value'),
                max_value=condition.get('max_value')
            )

        for change_col_name in change_cols:
            if change_col_name == BusinessUnitsModel.business_unit.name:
                change_col_name = BusinessUnitsModel.business_unit_id.name

            if change_col_name not in df.columns:
                raise ValueError(
                    f'Col {change_col_name} was passed but no such'
                    f' column on table {table_name}'
                )

            cat_choices = change_dict.get('categorical_values')
            if cat_choices is not None:
                if change_col_name == BusinessUnitsModel.business_unit_id.name:
                    bu_inserter = BusinessUnitInserter(
                        session=self.sql_session,
                        organization_id=self.target_organization_id,
                    )
                    cat_choices = [
                        bu_inserter._insert_row(
                            business_units=bu_name,
                            synchronisation_id=self.synchronization_id,
                        ) for bu_name in cat_choices
                    ]
                    self.sql_session.commit()

                    if table_name == VehicleAttributionsTable.__tablename__:
                        applicability &= (
                            pd.notna(df[change_col_name])
                        )

                df[change_col_name] = (
                    df[change_col_name].mask(
                        applicability,
                        df[change_col_name].apply(
                            lambda x: random.choice(cat_choices)
                        )
                    )
                )

            relative_changes = change_dict.get('relative_changes')
            if relative_changes is not None:
                df[change_col_name] = (
                    df[change_col_name].mask(
                        applicability,
                        df[change_col_name] *
                        random.choice(relative_changes)
                    )
                )

            absolute_changes = change_dict.get('absolute_changes')
            if absolute_changes is not None:
                df[change_col_name] = (
                    df[change_col_name].mask(
                        applicability,
                        df[change_col_name] +
                        random.choice(absolute_changes)
                    )
                )

        return df

    @staticmethod
    def extract_name_set(lexicon_path: str) -> list:
        """ Extract name set from lexicon path"""
        lexicon_table = pd.read_csv(lexicon_path, sep=";")
        name_set = list(lexicon_table['preusuel'].unique())
        name_set.remove('_PRENOMS_RARES')
        return name_set

    @classmethod
    def gen_choice_set(cls):
        choice_set = {letter: cls.LETTERS for letter in cls.LETTERS}
        choice_set.update(
            {number: cls.NUMBERS for number in cls.NUMBERS}
        )
        choice_set['-'] = tuple('-')
        return choice_set

    @staticmethod
    def apply_sql_condition(
        sql_col: sa.Column,
        categorical_values: typing.Optional[typing.Iterable],
        min_value: typing.Union[float, str, None],
        max_value: typing.Union[float, str, None],
    ) -> sa.ColumnElement:
        if categorical_values:
            if None in categorical_values:
                return sa.or_(
                    sql_col.is_(None),
                    sql_col.in_([val for val in categorical_values if val is not None])
                )
            return sql_col.in_(categorical_values)

        if (min_value is None) and (max_value is None):
            raise ValueError(
                'Condition must specify one of '
                'categorical_values, min_value, max_value '
                'but none were passed'
            )
        if not isinstance(
            sql_col.type,
            (
                sa.Integer,
                sa.Float,
                sa.Numeric,
                sa.Date,
                sa.DateTime,
                sa.TIMESTAMP,
            )
        ):
            raise ValueError(
                f'Cannot interpret min and/or max value condition '
                f'because column {sql_col.name} (dtype '
                f'{sql_col.type}) is not numeric or date'
            )

        if min_value is None:
            if isinstance(sql_col.type, (sa.Date, sa.DateTime, sa.TIMESTAMP)):
                return sql_col <= pd.Timestamp(max_value)
            else:
                return sql_col <= max_value

        elif max_value is None:
            if isinstance(sql_col.type, (sa.Date, sa.DateTime, sa.TIMESTAMP)):
                return sql_col >= pd.Timestamp(min_value)
            else:
                return sql_col >= min_value

        else:
            if isinstance(sql_col.type, (sa.Date, sa.DateTime, sa.TIMESTAMP)):
                return (
                    (sql_col >= pd.Timestamp(min_value)) &
                    (sql_col <= pd.Timestamp(max_value))
                )
            else:
                return (
                    (sql_col >= min_value) &
                    (sql_col <= max_value)
                )

    @staticmethod
    def apply_pandas_condition(
        col_series: pd.Series,
        categorical_values: typing.Optional[typing.Iterable],
        min_value: typing.Union[float, str, None],
        max_value: typing.Union[float, str, None],
    ) -> pd.Series:
        if categorical_values:
            return col_series.isin(categorical_values)

        if (min_value is None) and (max_value is None):
            raise ValueError(
                'Condition must specify one of '
                'categorical_values, min_value, max_value '
                'but none were passed'
            )
        if not (
            pd.api.types.is_numeric_dtype(
                col_series.dtype
            ) or
            pd.api.types.is_datetime64_any_dtype(
                col_series.dtype
            )
        ):
            raise ValueError(
                f'Cannot interpret min and/or max value condition '
                f'because column {col_series.name} (dtype '
                f'{col_series.dtype}) is not numeric'
            )

        if min_value is None:
            try:
                return col_series <= max_value
            except TypeError:
                return col_series <= pd.Timestamp(max_value)

        elif max_value is None:
            try:
                return col_series >= min_value

            except TypeError:
                return col_series >= pd.Timestamp(min_value)

        else:
            try:
                return (
                    (col_series >= min_value) &
                    (col_series <= max_value)
                )

            except TypeError:
                return (
                    (col_series >= pd.Timestamp(min_value)) &
                    (col_series <= pd.Timestamp(max_value))
                )

    def infer_vat(
        self: typing.Self,
        df: pd.DataFrame,
        vat_assumption: float = 0.2,
    ) -> pd.DataFrame:
        """ Infer VAT from available information in df.
        :param df: DataFrame with amount information must have at least one of
        amount_tax_exc or amount_tax_inc
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
            if ExpensesModel.soongo_category.name in df.columns:
                is_insurance = (
                    df[ExpensesModel.soongo_category.name].isin(
                        [
                            insurance_cat.value for insurance_cat
                            in InsurancePremiums
                        ]
                    )
                )
            else:
                is_insurance = pd.Series(False, index=df.index)

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
                    df[ExpensesModel.amount_tax_inc.name].mask(
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
        df[ExpensesModel.deductible_vat.name] = self.compute_deductible_vat(
            df=df,
            logger=logger,
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
        self: typing.Self,
        df: pd.DataFrame,
        logger: logging.Logger,
    ) -> pd.Series:
        """ Compute the deductible VAT for the expenses in the df

        :param df: DataFrame with expenses data
        :param logger: Logger object for logging

        :returns: Series with computed deductible VAT
        """
        if ExpensesModel.vat_value.name not in df.columns:
            raise ValueError(
                'vat_amount is required to compute deductible_vat. '
                'See infer_amounts_and_tax.'
            )
        if not (VehiclesModel.fiscal_type.name in df.columns):

            if 'vehicle_id' not in df.columns:
                raise ValueError(
                    'Vehicle id is required to compute deductible_vat.'
                )

            # If employee_id available then plate_number added by previous lines
            fiscal_type_df = pd.read_sql(
                sql=sa.select(
                    VehiclesTable.id.label('vehicle_id'),
                    VehiclesTable.fiscal_type,
                ),
                con=self.sql_session.bind,
            )
            df = df.merge(
                fiscal_type_df,
                on='vehicle_id',
                how='left',
                validate='m:1',
            )

        is_vu = (
            df[VehiclesModel.fiscal_type.name].isin(
                [
                    FiscalType.utility_car.value,
                    FiscalType.other.value,
                ]
            )
        ) & pd.notna(df[VehiclesModel.fiscal_type.name])

        if ExpensesModel.soongo_category.name in df.columns:
            not_rent = ~df[ExpensesModel.soongo_category.name].isin(
                [rent_cat.value for rent_cat in RentCategory]
            )
            deduc_vat = df[ExpensesModel.vat_value.name].where(
                is_vu | not_rent,
                0.0,
            )

            is_fuel = df[ExpensesModel.soongo_category.name].isin(
                (fuel_type.value for fuel_type in FuelTypes)
            )
            # Electricity is fully deductible
            electric_deduc = (
                (df[ExpensesModel.soongo_category.name] == FuelTypes.electricity.value)
            )

            deduc_vat = deduc_vat.mask(
                ~is_vu & is_fuel & ~electric_deduc,
                (0.8 * df[ExpensesModel.vat_value.name]).round(2),
            )

        elif ClaimsModel.expense_type.name in df.columns:
            not_fuel = (
                df[ClaimsModel.expense_type.name] !=
                ExpenseType.fuel.value
            )
            deduc_vat = df[ExpensesModel.vat_value.name].where(
                is_vu | not_fuel,
                (0.8 * df[ExpensesModel.vat_value.name]).round(2),
            )

        else:
            logger.warning(
                'No category provided. Assuming not fuel nor rent'
            )
            deduc_vat = df[ExpensesModel.vat_value.name]


def load_config() -> dict:
    """ Load the Sampler yaml config from the given path

    :param config_path: path

    :returns: list
    """
    with open(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'sampler_config.yaml',
        )
    ) as config_file:
        return yaml.safe_load(config_file)


def parse_args():
    """ Parse arguments passed to the Sampler
    """
    parser = argparse.ArgumentParser(
        description='Sample tables in a folder, creating synthetic data.'
    )

    parser.add_argument(
        '-o',
        '--organization-name',
        type=str,
        help='Name of the organization whose data to anonymize.',
    )
    parser.add_argument(
        '-s',
        '--source-organizations',
        type=str,
        nargs='+',
        default=[],
        help='organization to source the data from',
    )
    parser.add_argument(
        '--db-url',
        type=str,
        help='URL of the db to query',
    )
    parser.add_argument(
        '-n',
        '--name-lexicon',
        type=str,
        default='~/Documents/Data/Other/nat2022.csv',
        required=False,
        help='Path to fetch a name lexicon',
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=13,
        required=False,
        help='Random seed for anonymization. Default is 13.',
    )

    args = parser.parse_args()
    return args


def extract_name_set(lexicon_path: str) -> list:
    """ Extract name set from lexicon path"""
    lexicon_table = pd.read_csv(lexicon_path, sep=";")
    name_set = list(lexicon_table['preusuel'].unique())
    name_set.remove('_PRENOMS_RARES')
    return name_set


if __name__ == '__main__':
    args = parse_args()
    logger = gen_logger('sampler')
    config = load_config()
    session = gen_session(
        database_url=args.db_url,
    )
    sampler = Sampler(
        logger=logger,
        sql_session=session,
        target_organization_slug=args.organization_name,
        source_organizations=args.source_organizations,
        name_lexicon=args.name_lexicon,
        config=config,
    )

    sampler.push_anon_data_to_sql()

    logger.info(
        'All done, new data saved to organization %s',
        args.organization_name,
    )
