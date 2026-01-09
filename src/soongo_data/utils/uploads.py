from __future__ import annotations

import json
import logging
import re
import typing
import uuid
from datetime import datetime
from functools import lru_cache

import pandas as pd
import pytz
from sqlalchemy import JSON, Column, Engine, desc, func, insert, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm.session import Session

from soongo_data.data_models import (AccidentsModel, BusinessUnitsModel,
                                     CollaboratorsModel,
                                     EquipmentsModel, SoonGoRecordsModel,
                                     SuppliersModel, VehiclesModel)
from soongo_data.utils.db import list_timestamptz_columns
from soongo_data.sql_mappings import (AccidentsTable, BusinessUnitsTable,
                                      CollaboratorsTable,
                                      ConnectorsTable, EquipmentTable,
                                      OrganizationsTable, Regions,
                                      SuppliersTable, SynchronisationsTable,
                                      SynchronisationStatusTable,
                                      SynchronisationTypesTable,
                                      VehicleBrandsTable,
                                      VehicleManufacturersTable,
                                      VehicleModelsTable, VehiclesTable,
                                      VehicleTrimsTable)
from soongo_data.utils.enums import SynchronizationStatus as StatusEnum
from soongo_data.utils.type import (convert_string, df_is_nan, scalar_is_nan,
                                    series_is_nan, str_is_nan, series_equal)

if typing.TYPE_CHECKING:
    from soongo_data.utils.input_tables import InputColumn, InputTable


class BusinessUnitInserter:

    def __init__(
        self,
        session: Session,
        organization_id: uuid.UUID,
        matching_col: str = BusinessUnitsModel.business_unit.name,
    ) -> None:
        self.session = session
        self.organization_id = organization_id
        self.matching_col = matching_col

    @lru_cache
    def _get_business_unit_id(
        self: typing.Self,
        business_unit_name: str,
        parent_id: typing.Optional[uuid.UUID] = None,
    ) -> typing.Optional[uuid.UUID]:
        """ Internal method to get the business unit id from its name.

        Cached for efficiency reasons.

        :param business_unit_name: str name of the business unit
        :param parent_id: uuid id of the parent business unit

        :returns: uuid id of the business unit
        """
        if not business_unit_name:
            return None

        return self.session.query(BusinessUnitsTable.id).filter_by(
            name=business_unit_name,
            organization_id=self.organization_id,
            parent_id=parent_id
        ).scalar()

    def _insert_row(
        self: typing.Self,
        business_units: str,
        synchronisation_id: str,
    ) -> uuid.UUID:
        if not business_units:
            return None
        business_units = business_units.split(' > ')

        v_parent_id = None
        for v_business_unit_name in business_units:
            v_business_unit_id = self.session.query(BusinessUnitsTable.id).filter_by(
                name=v_business_unit_name,
                organization_id=self.organization_id,
                parent_id=v_parent_id
            ).scalar()

            if not v_business_unit_id:
                new_business_unit = BusinessUnitsTable(
                    name=v_business_unit_name,
                    organization_id=self.organization_id,
                    parent_id=v_parent_id,
                    original_synchronisation_id=synchronisation_id,
                )
                self.session.add(new_business_unit)
                self.session.flush()
                v_business_unit_id = new_business_unit.id

            v_parent_id = v_business_unit_id

        assert v_business_unit_id is not None, 'Insertion failed'
        return v_business_unit_id

    def insert_row(self, row_dict) -> uuid.uuid4:

        return self._insert_row(
            business_units=row_dict.get(self.matching_col),
            synchronisation_id=row_dict[SoonGoRecordsModel.synchronisation_id.name],
        )

    def insert_df(
        self: typing.Self,
        data_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """ Upserts business units in the db.

        :param data_df: DataFrame containing the business units
        :param session: SQLAlchemy session
        :param synchronisation_id: str synchronisation id
        :param organization_id: str organization_id

        :returns: DataFrame with the business unit ids
        """
        assert self.matching_col in data_df.columns, 'business_unit column not in data_df'
        bu_df = data_df.loc[
            ~series_is_nan(data_df[self.matching_col]),
            [
                self.matching_col,
                SoonGoRecordsModel.synchronisation_id.name
            ]
        ].drop_duplicates(subset=[self.matching_col])
        if bu_df.empty:
            data_df[BusinessUnitsModel.business_unit_id.name] = None
            return data_df
        bu_df[BusinessUnitsModel.business_unit_id.name] = bu_df[
            [
                self.matching_col,
                SoonGoRecordsModel.synchronisation_id.name
            ]
        ].apply(
            self.insert_row,
            axis=1,
        )
        assert not str_is_nan(bu_df[BusinessUnitsModel.business_unit_id.name]).any(), 'Some business unit ids are null'
        bu_df.drop(
            columns=SoonGoRecordsModel.synchronisation_id.name,
            inplace=True,
        )
        data_df = data_df.merge(
            bu_df,
            on=self.matching_col,
            how='left',
            validate='m:1',
        )
        assert (
            str_is_nan(data_df[BusinessUnitsModel.business_unit_id.name])
            ==
            str_is_nan(data_df[self.matching_col])
        ).all(), 'Some business unit ids not null whilst matching col is not'

        return data_df


class RegionInserter:

    def __init__(self, session: Session, organization_id: uuid.UUID):
        self.session = session
        self.organization_id = organization_id

    @lru_cache
    def _insert_region(
        self: typing.Self,
        synchronisation_id: str,
        regions: str,
    ) -> typing.Optional[uuid.UUID]:
        if not regions:
            return None
        regions = regions.split(' > ')

        v_parent_id = None
        for v_region_name in regions:
            v_region_id = self.session.query(Regions.id).filter_by(
                name=v_region_name,
                organization_id=self.organization_id,
                parent_id=v_parent_id
            ).scalar()

            if not v_region_id:
                new_region = Regions(
                    name=v_region_name,
                    organization_id=self.organization_id,
                    parent_id=v_parent_id,
                    original_synchronisation_id=synchronisation_id
                )
                self.session.add(new_region)
                self.session.flush()
                v_region_id = new_region.id

            v_parent_id = v_region_id

        return v_region_id

    def insert_row(self, row_dict) -> uuid.uuid4:

        return self._insert_region(
            synchronisation_id=row_dict[SoonGoRecordsModel.synchronisation_id.name],
            regions=row_dict.get(BusinessUnitsModel.geography.name),
        )

    def insert_df(
        self: typing.Self,
        data_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """ Upserts business units in the db.

        :param data_df: DataFrame containing the business units
        :param session: SQLAlchemy session
        :param synchronisation_id: str synchronisation id
        :param organization_id: str organization_id

        :returns: DataFrame with the business unit ids
        """
        assert BusinessUnitsModel.geography.name in data_df.columns, 'Geography column not in data_df'
        geo_df = data_df.loc[
            ~series_is_nan(data_df[BusinessUnitsModel.geography.name]),
            [
                BusinessUnitsModel.geography.name,
                SoonGoRecordsModel.synchronisation_id.name,
            ]
        ].drop_duplicates(subset=BusinessUnitsModel.geography.name)
        if geo_df.empty:
            data_df[BusinessUnitsModel.region_id.name] = None
            return data_df
        geo_df[BusinessUnitsModel.region_id.name] = geo_df[
            [
                BusinessUnitsModel.geography.name,
                SoonGoRecordsModel.synchronisation_id.name,
            ]
        ].apply(
            self.insert_row,
            axis=1,
        )
        data_df = data_df.merge(
            geo_df,
            on=[
                BusinessUnitsModel.geography.name,
                SoonGoRecordsModel.synchronisation_id.name,
            ],
            how='left',
            validate='m:1',
        )

        return data_df


class TrimInserter:
    MODEL_COLS = {
        VehiclesModel.make.name,
        VehiclesModel.model.name,
        VehiclesModel.model_category.name,
        VehiclesModel.full_model.name,
        SoonGoRecordsModel.synchronisation_id.name,
    }

    def __init__(self, session: Session, organization_id: uuid.uuid4) -> None:
        self.session = session
        self.organization_id = organization_id

    @lru_cache
    def _insert_make_model(
        self: typing.Self,
        synchronisation_id: str,
        make: str,
        model: str,
        model_category: str,
        full_model: str,
    ) -> typing.Dict[str, typing.Optional[uuid.UUID]]:
        v_constructor_id = None
        if not scalar_is_nan(make):
            v_constructor_id = self.session.query(VehicleManufacturersTable.id).filter_by(
                name=make
            ).scalar()

            if not v_constructor_id:
                new_constructor = VehicleManufacturersTable(
                    name=make,
                    original_synchronisation_id=synchronisation_id,
                )
                self.session.add(new_constructor)
                self.session.flush()
                v_constructor_id = new_constructor.id

        v_brand_id = None
        if not scalar_is_nan(make) and v_constructor_id:
            v_brand_id = self.session.query(VehicleBrandsTable.id).filter_by(
                name=make,
                manufacturer_id=v_constructor_id,
            ).scalar()

            if not v_brand_id:
                new_brand = VehicleBrandsTable(
                    name=make,
                    manufacturer_id=v_constructor_id,
                    original_synchronisation_id=synchronisation_id,
                )
                self.session.add(new_brand)
                self.session.flush()
                v_brand_id = new_brand.id

        v_models_id = None
        if not scalar_is_nan(model):
            v_models = self.session.query(VehicleModelsTable).filter_by(
                name=model,
                brand_id=v_brand_id,
            ).one_or_none()

            if v_models:
                v_models_id = v_models.id

            elif v_brand_id:
                v_models = VehicleModelsTable(
                    name=model,
                    brand_id=v_brand_id,
                    original_synchronisation_id=synchronisation_id,
                    model_category=model_category,
                )
                self.session.add(v_models)
                self.session.flush()
                v_models_id = v_models.id

        v_trim_id = None
        if not scalar_is_nan(full_model):
            v_trim_id = self.session.query(VehicleTrimsTable.id).filter_by(
                name=full_model,
                model_id=v_models_id,
            ).scalar()

            if not v_trim_id and v_models_id:
                new_trim = VehicleTrimsTable(
                    name=full_model,
                    model_id=v_models_id,
                    original_synchronisation_id=synchronisation_id,
                )
                self.session.add(new_trim)
                self.session.flush()
                v_trim_id = new_trim.id

        return {
            'manufacturer_id': v_constructor_id,
            'brand_id': v_brand_id,
            'model_id': v_models_id,
            'trim_id': v_trim_id,
        }

    def insert_row(self, row_dict) -> pd.Series:
        model_vars = {
            col_name: col_value
            for col_name, col_value in row_dict.items()
            if col_name in self.MODEL_COLS
        }

        if series_is_nan(pd.Series(list(model_vars.values()))).all():
            return pd.Series(
                {
                    'manufacturer_id': None,
                    'brand_id': None,
                    'model_id': None,
                    'trim_id': None,
                }
            )

        return pd.Series(
            self._insert_make_model(
                synchronisation_id=row_dict[SoonGoRecordsModel.synchronisation_id.name],
                make=row_dict[VehiclesModel.make.name],
                model=row_dict[VehiclesModel.model.name],
                model_category=row_dict.get(VehiclesModel.model_category.name),
                full_model=row_dict[VehiclesModel.full_model.name],
            )
        )

    def insert_df(
        self: typing.Self,
        data_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """ Upserts business units in the db.

        :param data_df: DataFrame containing the business units
        :param session: SQLAlchemy session
        :param synchronisation_id: str synchronisation id
        :param organization_id: str organization_id

        :returns: DataFrame with the business unit ids
        """
        assert self.MODEL_COLS.issubset(data_df.columns), f'Some of {self.MODEL_COLS} not in df columns {data_df.columns}'
        trim_df = data_df[list(self.MODEL_COLS)].drop_duplicates(
            subset=[
                VehiclesModel.make.name,
                VehiclesModel.model.name,
                VehiclesModel.model_category.name,
                VehiclesModel.full_model.name,
            ]
        )
        trim_df[
            [
                'manufacturer_id',
                'brand_id',
                'model_id',
                'trim_id',
            ]
        ] = trim_df.apply(
            self.insert_row,
            axis=1,
        )
        data_df = data_df.merge(
            trim_df,
            on=list(self.MODEL_COLS),
            how='left',
            validate='m:1',
        )

        return data_df


class SynchronisationInserter:
    RECORD_COLUMNS = [
        SoonGoRecordsModel.synchronisation_id.name,
        SoonGoRecordsModel.synchronisation_type.name,
        SoonGoRecordsModel.connector_id.name,
    ]

    def __init__(self, session: Session, organization_id: uuid.uuid4) -> None:
        self.session = session
        self.organization_id = organization_id

    @lru_cache
    def _insert_row(
        self: typing.Self,
        synchronisation_id: str,
        connector_id: str,
        synchronisation_type: str
    ) -> uuid.UUID:
        db_synchronization_id = self.session.query(
            SynchronisationsTable.id
        ).filter_by(id=synchronisation_id).one_or_none()
        if db_synchronization_id is not None:
            return synchronisation_id

        # Fetch connector_id, type_id, and status_id
        type_id = self.session.query(
            SynchronisationTypesTable.id
        ).filter_by(name=synchronisation_type).scalar()
        status_id = self.session.query(
            SynchronisationStatusTable.id
        ).filter_by(name=StatusEnum.ongoing.value).scalar()

        self.session.add(
            SynchronisationsTable(
                id=synchronisation_id,
                connector_id=str(connector_id),
                type_id=str(type_id),
                status_id=str(status_id),
                organization_id=str(self.organization_id),
            )
        )
        self.session.flush()

        return synchronisation_id

    def insert_row(self, row_dict) -> uuid.uuid4:

        return self._insert_row(
            synchronisation_id=row_dict[SoonGoRecordsModel.synchronisation_id.name],
            connector_id=row_dict[SoonGoRecordsModel.connector_id.name],
            synchronisation_type=row_dict[SoonGoRecordsModel.synchronisation_type.name],
        )

    def insert_df(self: typing.Self, data_df: pd.DataFrame) -> pd.DataFrame:
        """ Upserts business units in the db.

        :param data_df: DataFrame containing the business units
        :param session: SQLAlchemy session
        :param synchronisation_id: str synchronisation id
        :param organization_id: str organization_id

        :returns: DataFrame with the business unit ids
        """
        assert SoonGoRecordsModel.synchronisation_id.name in data_df.columns, 'synchronisation_id column not in data_df'
        sync_df = data_df[
            list(self.RECORD_COLUMNS)
        ].drop_duplicates()
        sync_df.apply(
            self.insert_row,
            axis=1,
        )
        # synchronisation id already in data_df, no need to merge
        return data_df


class SupplierInserter:

    def __init__(
        self,
        session: Session,
        organization_id: uuid.uuid4,
        supplier_col: str,
    ) -> None:
        self.session = session
        self.organization_id = organization_id
        self.supplier_col = supplier_col

    @lru_cache
    def _insert_row(
        self: typing.Self,
        supplier_name: str,
        synchronisation_id: str,
    ) -> uuid.UUID:
        if scalar_is_nan(supplier_name):
            return None

        supplier_id = self.session.query(
            SuppliersTable.id
        ).filter_by(name=supplier_name).scalar()
        if supplier_id is not None:
            return supplier_id

        new_supplier = SuppliersTable(
            name=supplier_name,
            original_synchronisation_id=synchronisation_id,
        )
        self.session.add(
            new_supplier
        )
        self.session.flush()

        return new_supplier.id

    def insert_row(self, row_dict) -> uuid.uuid4:

        return self._insert_row(
            synchronisation_id=row_dict[SoonGoRecordsModel.synchronisation_id.name],
            supplier_name=row_dict[self.supplier_col],
        )

    def insert_df(self: typing.Self, data_df: pd.DataFrame) -> pd.DataFrame:
        """ Upserts business units in the db.

        :param data_df: DataFrame containing the business units
        :param session: SQLAlchemy session
        :param synchronisation_id: str synchronisation id
        :param organization_id: str organization_id

        :returns: DataFrame with the business unit ids
        """
        assert SoonGoRecordsModel.synchronisation_id.name in data_df.columns, 'synchronisation_id column not in data_df'
        supplier_df = data_df[
            [
                self.supplier_col,
                SoonGoRecordsModel.synchronisation_id.name
            ]
        ].drop_duplicates()
        supplier_df[SuppliersModel.supplier_id.name] = supplier_df.apply(
            self.insert_row,
            axis=1,
        )

        missing_suppliers = supplier_df.loc[
            ~str_is_nan(supplier_df[self.supplier_col])
            & series_is_nan(supplier_df[SuppliersModel.supplier_id.name])
        ]
        if not missing_suppliers.empty:
            raise ValueError(
                f'Some suppliers were not inserted: {missing_suppliers[self.supplier_col].tolist()}'
            )

        supplier_df = supplier_df[
            [
                self.supplier_col,
                SuppliersModel.supplier_id.name,
            ]
        ].drop_duplicates()
        data_df = data_df.merge(
            supplier_df,
            on=self.supplier_col,
            how='left',
            validate='m:1',
        )

        if SuppliersModel.supplier_id.name not in data_df.columns:
            data_df[SuppliersModel.supplier_id.name] = None

        return data_df


def fetch_business_unit_id_from_name(
    logger: logging.Logger,
    session: Session,
    business_unit_name: str,
    organization_id: uuid,
):
    """ Method to get the db id of a business unit from its final entity name.

    Obsolete method, use get_business_unit instead.
    """
    logger.error('Obsolete method, use get_business_unit instead.')
    if scalar_is_nan(business_unit_name):
        return None

    # Query the database to get the business unit IDs
    results = session.query(
        func.array_agg(BusinessUnitsTable.id)
    ).filter(
        BusinessUnitsTable.name == business_unit_name,
        BusinessUnitsTable.organization_id == organization_id
    ).scalar()

    # Check the length of the results
    if results and len(results) == 1:
        return results[0]
    else:
        logger.error(
            (
                'Multiple business units with the same name %s found in the '
                'database for organization %s'
            ),
            business_unit_name,
            organization_id
        )
        return None


def upsert_car_trim(
    session: Session,
    constructor_name: str,
    model_name: str,
    brand_name: str,
    model_category_name: str,
    trim_name: str,
    synchronisation_id: str,
):

    v_constructor_id = None
    if not scalar_is_nan(constructor_name):
        v_constructor_id = session.query(VehicleManufacturersTable.id).filter_by(
            name=constructor_name
        ).scalar()

        if not v_constructor_id:
            new_constructor = VehicleManufacturersTable(
                name=constructor_name,
                original_synchronisation_id=synchronisation_id,
            )
            session.add(new_constructor)
            session.flush()
            v_constructor_id = new_constructor.id

    v_brand_id = None
    if not scalar_is_nan(brand_name) and v_constructor_id:
        v_brand_id = session.query(VehicleBrandsTable.id).filter_by(
            name=brand_name,
            manufacturer_id=v_constructor_id,
        ).scalar()

        if not v_brand_id:
            new_brand = VehicleBrandsTable(
                name=brand_name,
                manufacturer_id=v_constructor_id,
                original_synchronisation_id=synchronisation_id,
            )
            session.add(new_brand)
            session.flush()
            v_brand_id = new_brand.id

    v_models_id = None
    if not scalar_is_nan(model_name):
        v_models = session.query(VehicleModelsTable).filter_by(
            name=model_name,
            brand_id=v_brand_id,
        ).one_or_none()
        v_models_id = None

        if v_models is None and v_brand_id:
            v_models = VehicleModelsTable(
                name=model_name,
                brand_id=v_brand_id,
                original_synchronisation_id=synchronisation_id,
                model_category=model_category_name,
            )
            session.add(v_models)
            session.flush()

        elif (
            (v_models.model_category != model_category_name)
            and
            (not scalar_is_nan(model_category_name))
        ):
            v_models.model_category = model_category_name
            session.flush()

    v_trim_id = None
    if not scalar_is_nan(trim_name):
        v_trim_id = session.query(VehicleTrimsTable.id).filter_by(
            name=trim_name,
            model_id=v_models_id,
        ).scalar()

        if not v_trim_id and v_models_id:
            new_trim = VehicleTrimsTable(
                name=trim_name,
                model_id=v_models_id,
                original_synchronisation_id=synchronisation_id,
            )
            session.add(new_trim)
            session.flush()
            v_trim_id = new_trim.id

    return {
        'manufacturer_id': v_constructor_id,
        'brand_id': v_brand_id,
        'model_id': v_models_id,
        'trim_id': v_trim_id,
    }


def upsert_equipment(
    session: Session,
    equipment_reference: str,
    equipment_status: typing.Optional[str],
    equipment_supplier: typing.Optional[str],
    equipment_start_date: typing.Optional[pd.Timestamp],
    equipment_end_date: typing.Optional[pd.Timestamp],
    equipment_code: str,
    synchronisation_uuid: uuid.UUID,
    organization_id: uuid.UUID,
):
    """ Upserts an equipment reference in database.

    Note: collab/vehicle/bu attribution attributes are not uploaded as these
    columns are likely to have a different meaning outside of the equipment
    table upload process. To upload an attribution, upload the equipments
    table.

    """

    equipment = session.query(EquipmentTable).filter_by(
        equipment_reference=equipment_reference,
        organization_id=organization_id,
    ).one_or_none()

    if equipment is None:

        equipment_dict = {
            'equipment_reference': equipment_reference,
            'equipment_status': equipment_status,
            'equipment_supplier': equipment_supplier,
            'equipment_start_date': equipment_start_date,
            'equipment_end_date': equipment_end_date,
            'equipment_code': equipment_code,
            'organization_id': organization_id,
            'synchronisation_id': synchronisation_uuid,
        }
        equipment_dict = filter_null_values(equipment_dict)
        equipment = EquipmentTable(
            **equipment_dict
        )
        session.add(equipment)
        session.flush()

    else:

        for attr_name, attr_value in (
            ('equipment_reference', equipment_reference),
            ('equipment_status', equipment_status),
            ('equipment_supplier', equipment_supplier),
            ('equipment_start_date', equipment_start_date),
            ('equipment_end_date', equipment_end_date),
            ('equipment_code', equipment_code),
            ('organization_id', organization_id),
        ):

            if pd.notna(attr_value):
                setattr(
                    equipment,
                    attr_name,
                    attr_value,
                )
        session.flush()

    return equipment.id


def upsert_table(
    input_table: InputTable,
    insert_df: pd.DataFrame,
    session: Session,
    logger: logging.Logger,
    organization_id: uuid.UUID,
    id_cols: typing.Optional[typing.Dict[str, InputColumn]] = None,
    deduplicate_values: bool = False,
    update_values: str = 'null_only',
    batch_size: int = 10000,
    columns: typing.Optional[typing.List[str]] = None,
) -> pd.DataFrame:
    """ Attempts to inserts information contained in the df into the targeted
    sql_mapping. If the row already exists, fills in missing
    information in the table.

    Typically used for vehicles or collaborators: add vehicles and/or collab
    if not yet existing, fill in missing info if already existing.

    :param sql_mapping: SQLAlchemy declarative base table
    :param insert_df: pandas DataFrame relevant to that sql_mapping
    :param id_cols: cols uniquely identifying objects in the sql_mapping column
        other than the db id (typically plate_number for vehicles)
    :param session: SQLAlchemy session
    :param organization_id: uuid of the organization
    :param columns: columns to update. If None passed, all are updated.

    :returns: updated insert_df with the object id.
    """
    assert update_values in ('overwrite', 'null_only', 'keep', 'inc_null'), 'Invalid update_values'
    if id_cols is None:
        id_cols = input_table.get_id_cols()
    if not set(id_cols.keys()).issubset(insert_df.columns):
        raise ValueError(
            f'{id_cols.keys()} not in columns {insert_df.columns}'
        )

    assert 'id' not in insert_df.columns, 'duplicates flagged thanks to id column, cannot provide one already'

    insert_df = flag_duplicates(
        data_df=insert_df.copy(),
        sql_mapping=input_table.sql_mapping,
        id_cols=id_cols,
        logger=logger,
        session=session,
        organization_id=organization_id,
        date_col_name=input_table.date_col_name,
    )
    assert 'id' in insert_df.columns, 'id column not added by flag_duplicates'
    record_columns = [
        SoonGoRecordsModel.synchronisation_id.name,
        SoonGoRecordsModel.synchronisation_type.name,
        SoonGoRecordsModel.connector_id.name,
    ]
    sql_mapping_columns = set(input_table.sql_mapping.__table__.columns.keys())
    json_columns = set(
        col.name for col in input_table.sql_mapping.__table__.columns
        if isinstance(col.type, JSON) or isinstance(col.type, JSONB)
    )
    overlap_columns = set(insert_df.columns).intersection(
        sql_mapping_columns
    )
    if deduplicate_values:
        insert_df = deduplicate(
            dup_df=insert_df,
            id_cols=id_cols,
            cols_to_fetch=list(overlap_columns.union(record_columns))
        )

    # Insert new rows. Do not insert null id cols when these non nullable
    # e.g. null plate numbers or collaborator ids in vehicles and collab tables
    non_null_id_col_names = [
        col.sql_name for col in id_cols.values() if not col.nullable
    ]
    if non_null_id_col_names:
        id_cols_not_null = ~df_is_nan(insert_df[non_null_id_col_names]).any(axis=1)
    else:
        id_cols_not_null = pd.Series(True, index=insert_df.index)

    logger.warning(
        'Excluding %d rows with null non nullable id cols for table %s',
        len(insert_df) - id_cols_not_null.sum(),
        input_table.sql_mapping.__name__,
    )
    is_new = series_is_nan(insert_df['id'])

    update_rows = insert_df.loc[
        ~is_new & id_cols_not_null
    ]
    if (update_values != 'keep') and not update_rows.empty:

        # Update additional information
        logger.info(
            'Updating %d existing rows into table %s',
            len(update_rows),
            input_table.sql_mapping.__name__,
        )
        update_count = 0
        update_rows = [
            prepare_row_dict(
                row_dict=row_dict,
                organization_id=organization_id,
                json_columns=json_columns,
                sql_mapping_columns=sql_mapping_columns,
            )
            for row_dict in update_rows.to_dict(orient='records')
        ]
        for row_dict in update_rows:

            existing_row = session.query(input_table.sql_mapping).filter_by(
                id=row_dict['id']
            ).one()

            col_values = {
                col_name: col_value for col_name, col_value in row_dict.items()
                if col_name in columns
            } if columns else row_dict
            for column_name, column_value in col_values.items():

                if update_values == 'inc_null':
                    setattr(
                        existing_row,
                        column_name,
                        column_value
                    )

                elif not scalar_is_nan(column_value):
                    if (
                        (update_values == 'overwrite') or
                        scalar_is_nan(
                            getattr(existing_row, column_name)
                        )
                    ):
                        setattr(
                            existing_row,
                            column_name,
                            column_value
                        )

            update_count += 1
            session.flush()
            if update_count % 1000 == 0:
                logger.info(
                    'Updated %d rows in table %s',
                    update_count,
                    input_table.sql_mapping.__name__,
                )

    new_rows = insert_df.loc[
        is_new & id_cols_not_null  # If id is nan, then not yet in db
    ]

    if not new_rows.empty:
        logger.info(
            'Inserting %d new rows into table %s into batches of %d',
            len(new_rows),
            input_table.sql_mapping.__name__,
            batch_size,
        )

        new_rows_dict = [
            prepare_row_dict(
                row_dict=row_dict,
                organization_id=organization_id,
                json_columns=json_columns,
                sql_mapping_columns=sql_mapping_columns,
                drop_id=True,
            )
            for row_dict in new_rows.to_dict(orient='records')
        ]
        logger.info(
            'Rows prepared, starting insertion into table %s',
            input_table.sql_mapping.__name__,
        )

        insert_count = 0
        next_limit = min(batch_size, len(new_rows_dict))
        new_id_lst = []
        while insert_count < len(new_rows_dict):

            rows = new_rows_dict[insert_count:next_limit]
            sql_statement = insert(input_table.sql_mapping).values(
                rows
            ).returning(input_table.sql_mapping.id)

            ids = session.scalars(sql_statement)
            session.flush()

            new_id_lst.extend(ids)
            insert_count += len(rows)
            next_limit = min(insert_count + batch_size, len(new_rows_dict))
            logger.info(
                'Inserted %d rows out of %d in table %s',
                insert_count,
                len(new_rows_dict),
                input_table.sql_mapping.__name__,
            )

        # Fill in ids of new vehicles or collaborators
        assert len(new_id_lst) == len(new_rows_dict)
        insert_df.loc[
            is_new & id_cols_not_null,  # If id is nan, then not yet in db
            'id_new'
        ] = pd.Series(new_id_lst, index=new_rows.index)

        insert_df['id'] = insert_df['id'].mask(
            series_is_nan(insert_df['id']),
            insert_df['id_new'],
        )
        assert not series_is_nan(
            insert_df.loc[id_cols_not_null, 'id']
        ).any(), 'Some rows with a valid identifying col were not inserted into db'

    session.commit()
    logger.info(
        'Transaction committed on table %s',
        input_table.sql_mapping.__name__,
    )

    # Return insert_df with added id column
    return insert_df[list(id_cols.keys()) + ['id']]


def insert_sliding_table(
    input_table: InputTable,
    insert_df: pd.DataFrame,
    session: Session,
    logger: logging.Logger,
    organization_id: uuid.UUID,
    start_col: InputColumn,
    end_col: InputColumn,
    update_cols: typing.Collection[InputColumn],
    id_cols: typing.Optional[typing.Dict[str, InputColumn]] = None,
    update_values: str = 'null_only',
    batch_size: int = 1000,
    columns: typing.Optional[typing.List[str]] = None,
) -> pd.DataFrame:
    """ Attempts to inserts information contained in the df into the targeted
    sql_mapping. If the row already exists, fills in missing
    information in the table.

    Typically used for vehicles or collaborators: add vehicles and/or collab
    if not yet existing, fill in missing info if already existing.

    :param sql_mapping: SQLAlchemy declarative base table
    :param insert_df: pandas DataFrame relevant to that sql_mapping
    :param id_cols: cols uniquely identifying objects in the sql_mapping column
        other than the db id (typically plate_number for vehicles)
    :param session: SQLAlchemy session
    :param organization_id: uuid of the organization
    :param columns: columns to update. If None passed, all are updated.

    :returns: updated insert_df with the object id.
    """
    if id_cols is None:
        id_cols = input_table.get_id_cols()
    if not set(id_cols.keys()).issubset(insert_df.columns):
        raise ValueError(
            f'{id_cols.keys()} not in columns {insert_df.columns}'
        )

    assert 'id' not in insert_df.columns, 'duplicates flagged thanks to id column, cannot provide one already'

    insert_df = sliding_flag_duplicates(
        data_df=insert_df.copy(),
        sql_mapping=input_table.sql_mapping,
        id_cols=id_cols,
        logger=logger,
        session=session,
        organization_id=organization_id,
        start_col=start_col,
        end_col=end_col,
        update_cols=update_cols,
    )
    assert 'id' in insert_df.columns, 'id column not added by flag_duplicates'
    sql_mapping_columns = set(input_table.sql_mapping.__table__.columns.keys())
    json_columns = set(
        col.name for col in input_table.sql_mapping.__table__.columns
        if isinstance(col.type, JSON) or isinstance(col.type, JSONB)
    )

    # Insert new rows
    non_null_id_col_names = [
        col.name for col in id_cols.values() if not col.nullable
    ]
    if non_null_id_col_names:
        id_cols_not_null = ~df_is_nan(insert_df[non_null_id_col_names]).any(axis=1)
    else:
        id_cols_not_null = pd.Series(True, index=insert_df.index)
    is_new = series_is_nan(insert_df['id'])
    new_rows = insert_df.loc[
        is_new & id_cols_not_null  # If id is nan, then not yet in db
    ]

    if not new_rows.empty:
        logger.info(
            'Inserting %d new rows into table %s into batches of %d',
            len(new_rows),
            input_table.sql_mapping.__name__,
            batch_size,
        )

        new_rows_dict = [
            prepare_row_dict(
                row_dict=row_dict,
                organization_id=organization_id,
                json_columns=json_columns,
                sql_mapping_columns=sql_mapping_columns,
                drop_id=True,
            )
            for row_dict in new_rows.to_dict(orient='records')
        ]
        logger.info(
            'Rows prepared, starting insertion into table %s',
            input_table.sql_mapping.__name__,
        )

        insert_count = 0
        next_limit = min(batch_size, len(new_rows_dict))
        new_id_lst = []
        while insert_count < len(new_rows_dict):

            rows = new_rows_dict[insert_count:next_limit]
            sql_statement = insert(input_table.sql_mapping).values(
                rows
            ).returning(input_table.sql_mapping.id)

            ids = session.scalars(sql_statement)
            session.flush()

            new_id_lst.extend(ids)
            insert_count += len(rows)
            next_limit = min(insert_count + batch_size, len(new_rows_dict))
            logger.info(
                'Inserted %d rows out of %d in table %s',
                insert_count,
                len(new_rows_dict),
                input_table.sql_mapping.__name__,
            )

        # Fill in ids of new vehicles or collaborators
        assert len(new_id_lst) == len(new_rows_dict)
        insert_df.loc[
            is_new & id_cols_not_null,  # If id is nan, then not yet in db
            'id_new'
        ] = pd.Series(new_id_lst, index=new_rows.index)

        insert_df['id'] = insert_df['id'].mask(
            series_is_nan(insert_df['id']),
            insert_df['id_new'],
        )
        assert not series_is_nan(
            insert_df.loc[id_cols_not_null, 'id']
        ).any(), 'Some rows with a valid identifying col were not inserted into db'

    is_change = pd.Series(False, index=insert_df.index)
    for col in update_cols:

        if f'_previous_{col.sql_name}' not in insert_df.columns:
            is_change = pd.Series(True, index=insert_df.index)
            break
        else:
            is_change |= ~series_equal(
                insert_df[col.sql_name],
                insert_df[f'_previous_{col.sql_name}'],
                time_tolerance=pd.Timedelta('1 day'),
            )

    filling_rows = insert_df.loc[
        ~is_new & id_cols_not_null & ~is_change
    ]
    if not filling_rows.empty and (update_values != 'keep'):

        # Update additional information
        logger.info(
            'Filling %d existing rows into table %s, filling null values',
            len(filling_rows),
            input_table.sql_mapping.__name__,
        )
        fill_count = 0
        filling_rows = [
            prepare_row_dict(
                row_dict=row_dict,
                organization_id=organization_id,
                json_columns=json_columns,
                sql_mapping_columns=sql_mapping_columns,
            )
            for row_dict in filling_rows.to_dict(orient='records')
        ]
        for row_dict in filling_rows:

            existing_row = session.query(input_table.sql_mapping).filter_by(
                id=row_dict['id']
            ).one()

            col_values = {
                col_name: col_value for col_name, col_value in row_dict.items()
                if col_name in columns
            } if columns else row_dict

            for column_name, column_value in col_values.items():

                if update_values == 'inc_null':
                    setattr(
                        existing_row,
                        column_name,
                        column_value
                    )

                elif not scalar_is_nan(column_value):
                    if scalar_is_nan(
                        getattr(existing_row, column_name)
                    ):
                        setattr(
                            existing_row,
                            column_name,
                            column_value
                        )

            fill_count += 1
        session.flush()
        if fill_count % 1000 == 0:
            logger.info(
                'Filled %d rows in table %s',
                fill_count,
                input_table.sql_mapping.__name__,
            )

    update_rows = insert_df.loc[
        ~is_new & id_cols_not_null & is_change
    ]
    if not update_rows.empty and (update_values in ('overwrite', 'inc_null')):

        # Update additional information
        logger.info(
            (
                'Updating %d existing rows with non null changes into table %s'
                ', ending their validity and inserting new row'
            ),
            len(update_rows),
            input_table.sql_mapping.__name__,
        )
        update_count = 0
        update_rows = [
            prepare_row_dict(
                row_dict=row_dict,
                organization_id=organization_id,
                json_columns=json_columns,
                sql_mapping_columns=sql_mapping_columns,
            )
            for row_dict in update_rows.to_dict(orient='records')
        ]
        for row_dict in update_rows:

            existing_row = session.query(input_table.sql_mapping).filter_by(
                id=row_dict['id']
            ).one()

            col_values = {
                col_name: col_value for col_name, col_value in row_dict.items()
                if col_name in columns
            } if columns else row_dict

            setattr(
                existing_row,
                end_col.sql_name,
                row_dict[start_col.sql_name]
            )
            session.flush()

            col_values.pop('id')
            new_row = input_table.sql_mapping(**col_values)
            session.add(new_row)
            session.flush()

            update_count += 1
            session.flush()
            if update_count % 1000 == 0:
                logger.info(
                    'Inserted %d new update rows in table %s',
                    update_count,
                    input_table.sql_mapping.__name__,
                )

    session.commit()
    logger.info(
        'Transaction committed on table %s',
        input_table.sql_mapping.__name__,
    )

    # Return insert_df with added id column
    return insert_df[list(id_cols.keys()) + ['id']]


def deduplicate(
    dup_df: pd.DataFrame,
    id_cols: typing.List[str],
    cols_to_fetch: typing.List[str],
):
    id_col_lst = list(id_cols.keys())
    dedup_df = dup_df[id_col_lst].drop_duplicates()
    dedup_df = dedup_df.loc[
        pd.notna(dedup_df).any(axis=1)
    ]  # At least some id cols are not nan

    for col_name in cols_to_fetch:

        if (
            col_name not in dup_df.columns or
            col_name in id_col_lst
        ):
            continue

        # Identify non nan values
        data_cols = id_col_lst + [col_name]
        subset_df = dup_df.loc[
            (
                ~series_is_nan(dup_df[col_name]) &
                pd.notna(dup_df[id_col_lst]).any(axis=1)
            ),
            data_cols,
        ].drop_duplicates(data_cols)

        # For connector_id, dataset, and type, keep any
        if col_name in (
            SoonGoRecordsModel.connector_id.name,
            SoonGoRecordsModel.synchronisation_type.name,
            SoonGoRecordsModel.synchronisation_id.name,
        ):
            subset_df = subset_df.drop_duplicates(
                subset=[col for col in subset_df.columns if col != col_name]
            )

        # For the others, keep only unique values, conflicts are replaced with nan
        else:
            subset_df['dup_count'] = subset_df.groupby(
                id_col_lst
            )[id_col_lst[0]].transform('count')
            subset_df = subset_df.loc[subset_df['dup_count'] == 1, ]
            subset_df = subset_df.drop('dup_count', axis=1)
            assert subset_df[id_col_lst].duplicated().sum() == 0

        # Merge deduplicated column back into deduplicated df
        dedup_df = dedup_df.merge(
            right=subset_df[id_col_lst + [col_name]],
            on=id_col_lst,
            how='outer',
            indicator=True,
            validate='1:1',
        )
        assert dedup_df['_merge'].isin(['left_only', 'both']).all()
        dedup_df.drop('_merge', axis=1, inplace=True)

    return dedup_df


def flag_duplicates(
    data_df: pd.DataFrame,
    sql_mapping: DeclarativeMeta,
    id_cols: typing.Dict,
    session: Session,
    logger: logging.Logger,
    organization_id: str,
    date_col_name: typing.Optional[str] = None,
) -> pd.DataFrame:
    """ Flag insert rows already in db.

    :param data_df: DataFrame containing the raw connector data, some of which
    may be already in database
    :param id_cols: columns to uniquely identify the rows in the mapping.
    dictionary of column name to type.
    :param sql_mapping: SQLAlchemy mapping to upload this data into
    :param session: SQLAlchemy Session connected to the target db
    :param organization_id: organization uuid

    :returns: dataframe with only the rows not already contained in db
    """

    start_date, end_date = None, None
    if date_col_name:
        start_date = data_df[date_col_name].min()
        end_date = data_df[date_col_name].max()

    db_df = fetch_db_data(
        sql_mapping=sql_mapping,
        id_cols=id_cols,
        engine=session.get_bind(),
        logger=logger,
        organization_id=organization_id,
        date_col_name=date_col_name,
        start_date=start_date,
        end_date=end_date,
    )
    if db_df.empty:
        logger.warning('No data in db for table %s', sql_mapping.__name__)
        data_df['id'] = None
        return data_df

    # Merge connector data df with db data df for update detection
    return merge_db_data(
        connector_df=data_df,
        db_df=db_df,
        id_cols=db_df.columns,
    )


def sliding_flag_duplicates(
    data_df: pd.DataFrame,
    sql_mapping: DeclarativeMeta,
    id_cols: typing.Dict,
    start_col: InputColumn,
    end_col: InputColumn,
    update_cols: typing.Collection[InputColumn],
    session: Session,
    logger: logging.Logger,
    organization_id: str,
) -> pd.DataFrame:
    """ Flag insert rows already in db.

    :param data_df: DataFrame containing the raw connector data, some of which
    may be already in database
    :param id_cols: columns to uniquely identify the rows in the mapping.
    dictionary of column name to type.
    :param sql_mapping: SQLAlchemy mapping to upload this data into
    :param session: SQLAlchemy Session connected to the target db
    :param organization_id: organization uuid

    :returns: dataframe with only the rows not already contained in db
    """
    db_df = fetch_sliding_data(
        sql_mapping=sql_mapping,
        id_cols=id_cols,
        engine=session.get_bind(),
        logger=logger,
        start_col=start_col,
        end_col=end_col,
        update_cols=update_cols,
        organization_id=organization_id,
    ) 
    if db_df.empty:
        logger.warning('No data in db for table %s', sql_mapping.__name__)
        data_df['id'] = None
        return data_df

    # Merge connector data df with db data df for update detection
    return merge_db_data(
        connector_df=data_df,
        db_df=db_df,
        id_cols=list(id_cols.keys()),
    )


def merge_db_data(
    connector_df: pd.DataFrame,
    db_df: pd.DataFrame,
    id_cols: typing.Collection[str],
) -> pd.DataFrame:
    """ Merge connector data df with db data df for update detection.

    :param connector_df: DataFrame containing the raw connector data, some of
    which may be already in database
    :param db_df: DataFrame containing the data already in database
    :param id_cols: list of columns names to uniquely identify the rows.

    :returns: DataFrame with the merged data
    """
    merge_cols = []
    for col_name in id_cols:

        if pd.api.types.is_numeric_dtype(db_df[col_name].dtype):
            db_df[col_name] = convert_string(db_df[col_name].round(2))
            db_df.rename(
                {col_name: '_temp_' + col_name},
                axis=1,
                inplace=True,
            )
            connector_df['_temp_' + col_name] = convert_string(
                connector_df[col_name].round(2)
            )
            merge_cols.append('_temp_' + col_name)

        elif pd.api.types.is_datetime64_any_dtype(db_df[col_name].dtype):
            if db_df[col_name].dt.tz is not None:
                db_df[col_name] = db_df[col_name].dt.tz_convert('Europe/Paris').dt.tz_localize(None)

            merge_cols.append(col_name)

        elif col_name == 'add_params':
            db_df[col_name] = convert_string(db_df[col_name])
            # Db stores string with single quote, but connectors use double quotes
            db_df[col_name] = db_df[col_name].str.replace("'", '"')
            db_df.rename(
                {col_name: '_temp_' + col_name},
                axis=1,
                inplace=True,
            )
            connector_df['_temp_' + col_name] = convert_string(connector_df[col_name])
            connector_df['_temp_' + col_name] = connector_df['_temp_' + col_name].str.replace("'", '"')
            merge_cols.append('_temp_' + col_name)

        elif col_name != 'id':
            merge_cols.append(col_name)

    connector_df = connector_df.merge(
        how='left',
        right=db_df,
        on=merge_cols,
        indicator=False,
    )
    return connector_df[
        [col for col in connector_df.columns if not col.startswith('_temp_')]
    ]


def fetch_db_data(
    sql_mapping: DeclarativeMeta,
    id_cols: typing.Dict,
    engine: Engine,
    logger: logging.Logger,
    organization_id: typing.Optional[str] = None,
    date_col_name: typing.Optional[str] = None,
    start_date: typing.Optional[pd.Timestamp] = None,
    end_date: typing.Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """ Fetch database data, with all the rows at risk of duplication from
    the insert.

    :param sql_mapping: sql mapping to insert the data into
    :param id_cols: columns to uniquely identify the rows in the mapping
    :param engine: SQLAlchemy engine to that db
    :param logger: logger
    :param organization_id: organization uuid
    """
    # Build select statement (columns to query)
    substitute_col_dict = return_substitute_col_dict()
    mapping_cols = sql_mapping.__table__.columns.keys()
    query_columns = [
        substitute_col_dict.get(
            id_col,
            getattr(sql_mapping, id_col, None)
        )
        for id_col in id_cols.keys()
    ]
    if 'id' in mapping_cols:
        query_columns.append(sql_mapping.id)

    sql_query = select(*query_columns)

    # Build from statement (tables to query them from)
    sql_query = sql_query.select_from(sql_mapping)
    if VehiclesModel.vehicle_id.name in mapping_cols:
        sql_query = sql_query.outerjoin(
            VehiclesTable,
            VehiclesTable.id == sql_mapping.vehicle_id
        )

    if CollaboratorsModel.collaborator_id.name in mapping_cols:
        sql_query = sql_query.outerjoin(
            CollaboratorsTable,
            CollaboratorsTable.id == sql_mapping.collaborator_id
        )

    if EquipmentsModel.equipment_id.name in mapping_cols:
        sql_query = sql_query.outerjoin(
            EquipmentTable,
            EquipmentTable.id == sql_mapping.equipment_id
        )

    if BusinessUnitsModel.business_unit_id.name in mapping_cols:
        sql_query = sql_query.outerjoin(
            BusinessUnitsTable,
            BusinessUnitsTable.id == sql_mapping.business_unit_id
        )

    if SuppliersModel.supplier_id.name in mapping_cols:
        sql_query = sql_query.outerjoin(
            SuppliersTable,
            SuppliersTable.id == sql_mapping.supplier_id
        )

    where_conds = []
    if 'organization_id' in sql_mapping.__table__.columns:
        where_conds.append(
            sql_mapping.organization_id == organization_id
        )
    if pd.notna(start_date) and pd.notna(end_date):
        where_conds.append(
            getattr(
                sql_mapping,
                date_col_name,
            ).between(
                start_date - pd.Timedelta(days=1),
                end_date + pd.Timedelta(days=1),
            )
        )

    mapping_date_cols = list_timestamptz_columns(sql_mapping)
    mapping_date_cols = [
        col.name for col in query_columns if col.name in mapping_date_cols
    ]

    db_data = pd.read_sql(
        sql=sql_query.where(
            *where_conds
        ),
        con=engine,
        parse_dates=mapping_date_cols,
    )
    assert 'id' in db_data.columns, 'id column not fetched from db'

    # Dictionaries (not a type in pandas) not hashable
    if 'add_params' in id_cols:
        db_data['add_params'] = convert_string(db_data['add_params'])

    if db_data[list(id_cols.keys())].duplicated().any():
        logger.warning(
            'Some rows in the db for table %s have duplicate id columns %s',
            sql_mapping.__name__,
            id_cols.keys(),
        )
        # TODO: think about a better solution? as long as id_cols match
        # we don't really care about the rest of the columns
        db_data = db_data.sort_values('id')
        json_cols = [col_name for col_name, column in id_cols.items() if column.is_json]
        for col in json_cols:
            db_data[col] = convert_string(db_data[col])  # dictionary/list non hashable
        db_data = db_data.drop_duplicates(subset=list(id_cols.keys()))

    full_null_ids = df_is_nan(db_data[list(id_cols.keys())]).all(axis=1)
    if full_null_ids.any():
        logger.warning(
            'Some rows in the db for table %s have all id columns %s as null',
            sql_mapping.__name__,
            id_cols.keys(),
        )
        db_data = db_data[~full_null_ids]

    return db_data


def fetch_sliding_data(
    sql_mapping: DeclarativeMeta,
    id_cols: typing.Dict,
    engine: Engine,
    logger: logging.Logger,
    start_col: InputColumn,
    end_col: InputColumn,
    update_cols: typing.Collection[InputColumn],
    organization_id: typing.Optional[str] = None,
) -> pd.DataFrame:
    """ Fetch database data, with all the rows at risk of duplication from
    the insert.

    :param sql_mapping: sql mapping to insert the data into
    :param id_cols: columns to uniquely identify the rows in the mapping
    :param engine: SQLAlchemy engine to that db
    :param logger: logger
    :param organization_id: organization uuid
    """
    # Build select statement (columns to query)
    substitute_col_dict = return_substitute_col_dict()
    mapping_cols = sql_mapping.__table__.columns.keys()
    id_columns = [
        substitute_col_dict.get(
            id_col,
            getattr(sql_mapping, id_col, None)
        )
        for id_col in id_cols.keys()
    ]
    date_columns = [
        getattr(sql_mapping, start_col.sql_name).label(f'_previous_{start_col.sql_name}'),
        getattr(sql_mapping, end_col.sql_name).label(f'_previous_{end_col.sql_name}'),
    ]
    query_columns  = id_columns + date_columns
    if 'id' in mapping_cols:
        query_columns.append(sql_mapping.id)
    query_columns += [
        getattr(sql_mapping, col_name.sql_name).label(f'_previous_{col_name.sql_name}')
        for col_name in update_cols
    ]
    query_columns.append(
        func.rank().over(
            partition_by=id_columns,
            order_by=[
                desc(getattr(sql_mapping, start_col.sql_name)),
                desc(func.coalesce(getattr(sql_mapping, end_col.sql_name), func.now())),
            ],
        ).label('_rank_')
    )

    sql_query = select(*query_columns)

    # Build from statement (tables to query them from)
    sql_query = sql_query.select_from(sql_mapping)
    if VehiclesModel.vehicle_id.name in mapping_cols:
        sql_query = sql_query.outerjoin(
            VehiclesTable,
            VehiclesTable.id == sql_mapping.vehicle_id
        )

    if CollaboratorsModel.collaborator_id.name in mapping_cols:
        sql_query = sql_query.outerjoin(
            CollaboratorsTable,
            CollaboratorsTable.id == sql_mapping.collaborator_id
        )

    if EquipmentsModel.equipment_id.name in mapping_cols:
        sql_query = sql_query.outerjoin(
            EquipmentTable,
            EquipmentTable.id == sql_mapping.equipment_id
        )

    if BusinessUnitsModel.business_unit_id.name in mapping_cols:
        sql_query = sql_query.outerjoin(
            BusinessUnitsTable,
            BusinessUnitsTable.id == sql_mapping.business_unit_id
        )

    where_conds = []
    if 'organization_id' in sql_mapping.__table__.columns:
        where_conds.append(
            sql_mapping.organization_id == organization_id
        )

    logger.info(sql_query.compile(engine))

    db_data = pd.read_sql(
        sql=sql_query.where(
            *where_conds
        ),
        con=engine,
    )
    db_data = db_data.loc[
        db_data['_rank_'] == 1,
        db_data.columns.difference(['_rank_']),
    ]

    # Drop timezone information and convert
    date_cols = [
        f'_previous_{col.sql_name}'
        for col in update_cols + [start_col, end_col]
        if re.match(r'datetime.*', col.dtype, re.IGNORECASE)
    ]
    for col in date_cols:
        db_data[col] = pd.to_datetime(
            db_data[col],
            format='ISO8601',
            errors='coerce',
        )
        if db_data[col].dt.tz is not None:
            db_data[col] = db_data[col].dt.tz_convert('Europe/Paris')
            db_data[col] = pd.to_datetime(
                db_data[col].dt.tz_localize(None)
            )

    assert 'id' in db_data.columns, 'id column not fetched from db'
    assert not db_data[list(id_cols.keys())].duplicated().any(), 'id columns not unique'

    return db_data


def return_substitute_col_dict() -> typing.Dict[str, Column]:
    """ Return a substitute_col_dict, mapping column names to SQLAlchemy
    mapping columns.

    TODO: replace this substitute_col_dict with a better solution
    Ideally we would have already replaced plate_numbers with id at this
    stage, and same for the others. Just complexity in dealing with 'id' vs
    'vehicle_id' or 'collaborator_id'.

    :return: dictionary mapping column names to SQLAlchemy mapping columns
    """
    return {
        VehiclesModel.plate_number.name: getattr(
            VehiclesTable,
            VehiclesModel.plate_number.name,
        ),
        CollaboratorsModel.soongo_collab_reference.name: getattr(
            CollaboratorsTable,
            CollaboratorsModel.soongo_collab_reference.name,
        ),
        EquipmentsModel.equipment_reference.name: getattr(
            EquipmentTable,
            EquipmentsModel.equipment_reference.name,
        ),
        BusinessUnitsModel.business_unit.name: getattr(
            BusinessUnitsTable,
            'id',
        ).label(BusinessUnitsModel.business_unit_id.name),
    }


def type_value(uuid_str: typing.Union[str, uuid.UUID]) -> str:
    if isinstance(uuid_str, uuid.UUID):
        return str(uuid_str)

    if isinstance(uuid_str, pd.Timestamp) or isinstance(uuid_str, datetime):
        if pd.notna(uuid_str) and uuid_str.tzinfo is None:  # NaT cannot be localized
            uuid_str = pytz.timezone('Europe/Paris').localize(uuid_str)

    return uuid_str if str(uuid_str).lower() not in ('', 'nan', 'nat') else None


def prepare_row_dict(
    row_dict: dict,
    organization_id: uuid.UUID,
    json_columns: typing.List[str],
    sql_mapping_columns: typing.List[str],
    drop_id: bool = False,
):
    """
    Prepare a row dictionary for insertion into the database.
    Converts JSON columns to Python objects and ensures UUIDs are strings.
    :param row_dict: Dictionary representing a row of data.
    :param organization_id: UUID of the organization.
    :param json_columns: List of column names that should be treated as JSON.
    :param sql_mapping_columns: List of column names that are part of the SQL mapping.
    :param drop_id: Whether to drop the 'id' key from the row_dict.

    :return: Processed row dictionary ready for insertion.
    """

    row_dict = {
        col_name: (
            json.loads(col_value) if col_name in json_columns
            else type_value(col_value)
        )
        for col_name, col_value in row_dict.items()
        if col_name in sql_mapping_columns
    }
    if 'organization_id' in sql_mapping_columns:
        row_dict['organization_id'] = str(organization_id)
    if drop_id:
        row_dict.pop('id', None)

    return row_dict


def fetch_connector_ids(
    session: Session,
    data_df: pd.DataFrame,
) -> pd.DataFrame:
    """ Fetch connector ids from the db, and merge them into the data_df.
    """
    connector_id_df = pd.read_sql(
        sql=select(
            ConnectorsTable.id.label(SoonGoRecordsModel.connector_id.name),
            ConnectorsTable.name.label(SoonGoRecordsModel.connector_name.name),
        ),
        con=session.get_bind(),
    )
    data_df = data_df.merge(
        right=connector_id_df,
        how='left',
        on=SoonGoRecordsModel.connector_name.name,
        validate='m:1',
    )

    assert not series_is_nan(
        data_df.loc[
            data_df[SoonGoRecordsModel.connector_name.name].notna(),
            SoonGoRecordsModel.connector_id.name
        ]
    ).any(), 'Some connector names not found in db'

    return data_df


def fetch_business_unit_ids(
    session: Session,
    data_df: pd.DataFrame,
    entity_col_name: str,
    organization_id: uuid.UUID,
    logger: logging.Logger,
) -> pd.Series:
    logger.warning('Obsolete method, use get_business_unit instead.')
    entity_ref_df = pd.read_sql(
        sql=select(
            BusinessUnitsTable.name.label(entity_col_name),
            BusinessUnitsTable.id.label(BusinessUnitsModel.business_unit_id.name),
        ).select_from(
            BusinessUnitsTable
        ).join(
            OrganizationsTable,
            BusinessUnitsTable.organization_id == OrganizationsTable.id,
        ).where(
            OrganizationsTable.id == organization_id,
        ),
        con=session.get_bind(),
    )
    entity_ref_df['dup_count'] = entity_ref_df.groupby(
        entity_col_name
    ).transform('count')
    if (entity_ref_df['dup_count'] > 1).any():
        count_before = len(entity_ref_df)
        dup_bus = entity_ref_df.loc[
            entity_ref_df['dup_count'] > 1,
            entity_col_name,
        ].unique().tolist()
        entity_ref_df = entity_ref_df.loc[
                entity_ref_df['dup_count'] == 1
        ]
        entity_ref_df = entity_ref_df.drop(columns='dup_count')
        logger.warning(
            'Multiple business units with the same entity ref found in the'
            'data_df. dropping %d duplicates: %s',
            count_before - len(entity_ref_df),
            dup_bus,
        )

    data_df = data_df.merge(
        entity_ref_df,
        on=entity_col_name,
        how='left',
        validate='m:1',
    )
    return data_df[BusinessUnitsModel.business_unit_id.name]


def fetch_accident_ids(
    session: Session,
    data_df: pd.DataFrame,
    organization_id: uuid.UUID,
) -> pd.DataFrame:
    accident_id_df = pd.read_sql(
        sql=select(
            AccidentsTable.accident_ref.label(
                AccidentsModel.accident_ref.name
            ),
            AccidentsTable.id.label('temp_' + AccidentsModel.accident_id.name),
        ).select_from(
            AccidentsTable
        ).where(
            AccidentsTable.organization_id == organization_id,
            AccidentsTable.accident_ref.isnot(None),
            func.btrim(AccidentsTable.accident_ref) != ''
        ),
        con=session.get_bind(),
    )

    data_df = data_df.merge(
        accident_id_df,
        on=AccidentsModel.accident_ref.name,
        how='left',
        validate='m:1',
    )
    if AccidentsModel.accident_id.name in data_df.columns:
        data_df[AccidentsModel.accident_id.name] = (
            data_df[AccidentsModel.accident_id.name].fillna(
                data_df['temp_' + AccidentsModel.accident_id.name]
            )
        )
    else:
        data_df[AccidentsModel.accident_id.name] = (
            data_df['temp_' + AccidentsModel.accident_id.name]
        )

    data_df.drop(
        columns=['temp_' + AccidentsModel.accident_id.name],
        inplace=True
    )

    return data_df


def filter_null_values(insert_dict: dict) -> dict:
    return {
        key: value for key, value in insert_dict.items() if (
            pd.notna(value) and (value not in ('', 'nan', 'NaT'))
        )
    }
