from sqlalchemy import UUID, Column, DateTime, ForeignKey, Text, func
from sqlalchemy.schema import Index

from soongo_data.sql_mappings.base import Base


class VehicleManufacturersTable(Base):
    __tablename__ = 'vehicle_manufacturers'
    __table_args__ = (
        Index('vehicle_manufacturers_created_at_idx', 'created_at'),
        Index('vehicle_manufacturers_name_idx', 'name'),
        Index('vehicle_manufacturers_original_synchronisation_id_idx', 'original_synchronisation_id'),
        Index('vehicle_manufacturers_updated_at_idx', 'updated_at'),
        {'schema': 'common'}
    )

    id = Column(UUID, primary_key=True, server_default=func.uuid_generate_v4(), nullable=False)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    original_synchronisation_id = Column(UUID, ForeignKey('common.synchronisations.id'), nullable=True)


class VehicleBrandsTable(Base):
    __tablename__ = 'vehicle_brands'
    __table_args__ = (
        Index('vehicle_brands_created_at_idx', 'created_at'),
        Index('vehicle_brands_id_idx', 'id'),
        Index('vehicle_brands_manufacturer_id_idx', 'manufacturer_id'),
        Index('vehicle_brands_name_idx', 'name'),
        Index('vehicle_brands_original_synchronisation_id_idx', 'original_synchronisation_id'),
        Index('vehicle_brands_updated_at_idx', 'updated_at'),
        {'schema': 'common'}
    )

    id = Column(UUID, primary_key=True, server_default=func.uuid_generate_v4(), nullable=False)
    name = Column(Text, nullable=False)
    manufacturer_id = Column(
        UUID,
        ForeignKey('common.vehicle_manufacturers.id', ondelete='CASCADE'),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    original_synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id'),
        nullable=True,
    )


class VehicleModelsTable(Base):
    __tablename__ = 'vehicle_models'
    __table_args__ = (
        Index('vehicle_models_brand_id_idx', 'brand_id'),
        Index('vehicle_models_created_at_idx', 'created_at'),
        Index('vehicle_models_id_idx', 'id'),
        Index('vehicle_models_name_idx', 'name'),
        Index('vehicle_models_original_synchronisation_id_idx', 'original_synchronisation_id'),
        Index('vehicle_models_updated_at_idx', 'updated_at'),
        {'schema': 'common'}
    )

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
        nullable=False,
    )
    name = Column(Text, nullable=False)
    brand_id = Column(UUID, ForeignKey('common.vehicle_brands.id'))
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    original_synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id'),
        nullable=True,
    )
    model_category = Column(
        Text,
        ForeignKey('common.vehicle_model_categories.type', ondelete='SET NULL'),
    )


class VehicleTrimsTable(Base):
    __tablename__ = 'vehicle_trims'
    __table_args__ = (
        Index('vehicle_trims_created_at_idx', 'created_at'),
        Index('vehicle_trims_id_idx', 'id'),
        Index('vehicle_trims_model_id_idx', 'model_id'),
        Index('vehicle_trims_name_idx', 'name'),
        Index('vehicle_trims_original_synchronisation_id_idx', 'original_synchronisation_id'),
        Index('vehicle_trims_updated_at_idx', 'updated_at'),
        {'schema': 'common'}
    )

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
        nullable=False,
    )
    name = Column(Text, nullable=True)
    model_id = Column(
        UUID,
        ForeignKey('common.vehicle_models.id', ondelete='SET NULL'),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    original_synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id'),
        nullable=True,
    )
