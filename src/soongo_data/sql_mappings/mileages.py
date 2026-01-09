""" Mileages table definition and association tables """

from sqlalchemy import (TIMESTAMP, UUID, Column, Float, ForeignKey, Integer,
                        Text, Numeric, func)

from soongo_data.sql_mappings.base import Base


class MileagesTable(Base):
    __tablename__ = 'mileages'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    organization_id = Column(
        UUID,
        ForeignKey('common.organizations.id', ondelete='cascade'),
    )
    vehicle_id = Column(
        UUID,
        ForeignKey('publ.vehicles.id', ondelete='cascade'),
    )
    mileage = Column(Integer, nullable=False)
    mileage_date = Column(TIMESTAMP)
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
    )


class MileagesDiffTable(Base):
    __tablename__ = 'mileage_diff_days_diff'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        ForeignKey('publ.mileages.id', ondelete='cascade'),
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    organization_id = Column(
        UUID,
        ForeignKey('common.organizations.id', ondelete='cascade'),
    )
    vehicle_id = Column(
        UUID,
        ForeignKey('publ.vehicles.id', ondelete='cascade'),
    )
    mileage = Column(Integer, nullable=False)
    mileage_date = Column(TIMESTAMP)
    mileage_diff = Column(Float)
    days_diff = Column(Float)


class MileagePrimitiveView(Base):
    __tablename__ = "mileage_primitive_view"
    __table_args__ = {"schema": "publ"}

    mileage_attribution_id = Column(UUID, primary_key=True)
    date_from = Column(TIMESTAMP)
    date_to = Column(TIMESTAMP)
    organization_id = Column(UUID, nullable=False)
    vehicle_id = Column(UUID, nullable=False)
    collaborator_id = Column(UUID, nullable=False)
    cost_center_id = Column(UUID, nullable=False)
    attribution_id = Column(UUID, nullable=False)
    entry_into_fleet_date = Column(TIMESTAMP)
    exit_from_fleet_date = Column(TIMESTAMP)
    initial_mileage = Column(Integer)
    contract_type = Column(Text)
    mileage_month = Column(TIMESTAMP)
    co2_production = Column(Float)
    co2_recycling = Column(Float)
    first_mileage_date = Column(TIMESTAMP)
    first_mileage = Column(Float)
    last_mileage_date = Column(TIMESTAMP)
    last_mileage = Column(Float)
    first_mileage_diff = Column(Float)
    first_days_diff = Column(Numeric)
    next_mileage_diff = Column(Float)
    next_days_diff = Column(Numeric)
    mileage_driven = Column(Float)
