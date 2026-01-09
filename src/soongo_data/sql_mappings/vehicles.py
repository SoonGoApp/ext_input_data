""" Vehicles table definition and association tables """

from sqlalchemy import (JSON, TIMESTAMP, UUID, VARCHAR, Boolean, Column, Date, Float,
                        ForeignKey, Integer, String, Text, UniqueConstraint,
                        case, func)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

from soongo_data.sql_mappings.base import Base


class VehiclesTable(Base):
    __tablename__ = 'vehicles'
    __table_args__ = {'schema': 'publ'}
    id = Column(
        UUID,
        primary_key=True,
        nullable=False,
        server_default=func.uuid_generate_v4()
    )
    plate_number = Column(
        Text,
        nullable=False,
    )
    organization_id = Column(
        UUID,
        ForeignKey('common.organizations.id', ondelete='cascade'),
        nullable=False,
    )
    trim_id = Column(
        UUID,
        ForeignKey('common.vehicle_trims.id', ondelete='set null'),
    )
    model_id = Column(
        UUID,
        ForeignKey('common.vehicle_models.id', ondelete='set null'),
    )
    brand_id = Column(
        UUID,
        ForeignKey('common.vehicle_brands.id', ondelete='set null'),
    )
    manufacturer_id = Column(
        UUID,
        ForeignKey('common.vehicle_manufacturers.id', ondelete='set null'),
    )
    co2_per_km = Column(Float)
    co2_production = Column(Float)
    co2_recycling = Column(Float)
    energy = Column(Text)
    manufacturer_price_tax_exc = Column(Float)
    rebate_rate = Column(Float)
    rebate_price = Column(Float)
    order_reference = Column(Text, nullable=False)
    lease_start_date = Column(Date)
    lease_end_date = Column(Date)
    vehicle_status = Column(Text)
    lease_months = Column(Integer)
    lease_mileage = Column(Integer)
    vehicle_age = Column(Integer)
    supplier_id = Column(UUID, ForeignKey('common.suppliers.id'), nullable=True)
    initial_mileage = Column(Integer)
    mileage = Column(Integer)
    mileage_update = Column(TIMESTAMP)
    fiscal_power = Column(Integer)
    fiscal_type = Column(Text)
    is_air_quality_certified = Column(Boolean)
    seat_count = Column(Integer)
    business_unit_id = Column(UUID)
    theoretical_fuel_consumption = Column(Float)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    contract_type = Column(Text)
    entry_into_service_date = Column(Date)
    assignment_type = Column(Text)
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
    )
    entry_into_fleet_date = Column(Date)
    exit_from_fleet_date = Column(Date)
    model_version = Column(Text)
    color = Column(Text)
    door_count = Column(Integer)
    electricity_consumption = Column(Integer)
    battery_capacity = Column(Integer)
    battery_price = Column(Float)
    charge_power = Column(Float)
    transmission = Column(Text)
    critair = Column(Text)
    curb_weight = Column(Float)
    motor_power = Column(Integer)
    fuel_tank_capacity = Column(Float)
    vin = Column(
        VARCHAR(17),
        nullable=True
    )
    national_type = Column(Text)


def spread_co2_prod(mileage_col):
    return case(
        (mileage_col < 50000, mileage_col / 100000),
        (mileage_col < 100000, mileage_col / 200000 + 0.25),
        (mileage_col < 200000, mileage_col / 400000 + 0.5),
        (mileage_col >= 200000, 1),
    )


def spread_co2_recycling(mileage_col):
    return case(
        (mileage_col < 100000, mileage_col / 400000),
        (mileage_col < 150000, mileage_col / 200000 - 0.25),
        (mileage_col < 200000, mileage_col / 100000 - 1),
        (mileage_col >= 200000, 1),
    )


class VehicleConnectorIdsTable(Base):
    __tablename__ = 'vehicle_connector_ids'
    __table_args__ = (
        UniqueConstraint(
            'vehicle_id',
            'connector_id',
            'add_params',
            name='unique_vehicle_connector',
        ),
        {'schema': 'publ'}
    )

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.gen_random_uuid()
    )
    vehicle_id = Column(
        UUID,
        ForeignKey('publ.vehicles.id', ondelete='CASCADE'),
        nullable=False,
    )
    connector_id = Column(
        UUID,
        ForeignKey('common.connectors.id', ondelete='CASCADE'),
        nullable=False,
    )
    vehicle_connector_id = Column(
        String,
        nullable=False,
    )
    organization_id = Column(
        UUID,
        ForeignKey('common.organizations.id', ondelete='CASCADE'),
        nullable=False,
    )
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='CASCADE'),
    )
    add_params = Column(
        JSONB,
        nullable=True,
    )


class VehicleModelCategory(Base):
    __tablename__ = 'vehicle_model_categories'
    __table_args__ = {'schema': 'common'}

    type = Column(Text, primary_key=True, nullable=False)
    description = Column(Text, nullable=True)


class VehicleStatusHistoryTable(Base):
    __tablename__ = 'vehicle_status_history'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
        nullable=False,
    )
    status = Column(Text)
    vehicle_id = Column(
        UUID,
        nullable=False,
    )
    date_from = Column(
        TIMESTAMP(timezone=True)
    )
    date_to = Column(
        TIMESTAMP(timezone=True)
    )
    reason_id = Column(UUID)
    created_by = Column(UUID)


class VehicleView(Base):
    __tablename__ = 'vehicles_view'
    __table_args__ = {'schema': 'publ'}

    id = Column(UUID, primary_key=True)
    organization_id = Column(UUID)
    organization_slug = Column(Text)
    assignment_type = Column(Text)
    fiscal_type = Column(Text)
    energy = Column(Text)
    vehicle_status = Column(Text)
    status_reason = Column(Text)
    contract_type = Column(Text)
    plate_number = Column(Text)
    plate_number_compact = Column(Text)
    lease_start_date = Column(Date)
    lease_end_date = Column(Date)
    lease_months = Column(Integer)
    lease_mileage = Column(Integer)
    entry_into_fleet_date = Column(TIMESTAMP(timezone=True))
    exit_from_fleet_date = Column(TIMESTAMP(timezone=True))
    entry_into_service_date = Column(Date)
    mileage = Column(Float)
    mileage_date = Column(TIMESTAMP(timezone=True))
    fiscal_power = Column(Integer)
    co2_per_km = Column(Float)
    theoretical_fuel_consumption = Column(Float)
    seat_count = Column(Integer)
    door_count = Column(Integer)
    color = Column(Text)
    rebate_price = Column(Float)
    rebate_rate = Column(Float)
    manufacturer_price_tax_exc = Column(Float)
    manufacturer = Column(Text)
    supplier_name = Column(Text)
    trim = Column(Text)
    model_category = Column(Text)
    model = Column(Text)
    model_id = Column(UUID)
    make = Column(Text)
    current_association_id = Column(UUID)
    driver_collaborator_name = Column(Text)
    driver_collaborator_bu_name = Column(Text)
    driver_name = Column(Text)
    driver_bu_name = Column(Text)
    association_collaborator_id = Column(UUID)
    association_business_unit_id = Column(UUID)
    has_fuel_card = Column(Boolean)
    nb_equipments = Column(Integer)
    nb_contracts = Column(Integer)
    cost_center_id = Column(UUID)
    cost_center = Column(Text)
    last_update = Column(TIMESTAMP(timezone=True))
    tag_list = Column(Text)
    tag_associations = Column(JSON)
    excess_mileage = Column(Integer)
    search_index = Column(TSVECTOR)
    search_trgm = Column(Text)


class VehicleBusinessUnitView(Base):
    __tablename__ = 'vehicle_business_unit_view'
    __table_args__ = {'schema': 'publ'}

    # Note that the view does not truly have primary keys but
    # The vehicle_id, date_from, date_to does uniquely identifies rows and
    # (ii) passing a primary key is required by SQLAlchemy mapper
    vehicle_id = Column(UUID, primary_key=True)
    attribution_business_unit_id = Column(UUID)
    cost_center_id = Column(UUID)
    cost_center = Column(Text)
    date_from = Column(TIMESTAMP(timezone=True), primary_key=True)
    rank = Column(Integer)
    collaborator_id = Column(UUID)
    original_date_to = Column(TIMESTAMP(timezone=True))
    date_to = Column(TIMESTAMP(timezone=True), primary_key=True)
    previous_attribution_id = Column(
        UUID,
        ForeignKey('collaborators_vehicles.id', ondelete='cascade'),
    )
