from sqlalchemy import TIMESTAMP, UUID, Column, Integer, String, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class VehicleServicesTable(Base):
    __tablename__ = 'vehicle_services'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        nullable=False,
        default=func.gen_random_uuid()
    )
    vehicle_id = Column(UUID, nullable=False)
    mileage = Column(Integer, nullable=True)
    computed_service_date = Column(TIMESTAMP(timezone=True), nullable=False)
    scheduled_service_date = Column(TIMESTAMP(timezone=True), nullable=True)
    effective_service_date = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
    )
    updated_by = Column(UUID, nullable=True)
    organization_id = Column(
        UUID,
        nullable=False,
    )
    synchronisation_id = Column(
        UUID,
        nullable=True,
    )


class VehicleControls(Base):
    __tablename__ = 'vehicle_controls'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        nullable=False,
        server_default=func.gen_random_UUID()
    )
    vehicle_id = Column(UUID, nullable=False)
    computed_control_date = Column(TIMESTAMP(timezone=True), nullable=False)
    scheduled_control_date = Column(TIMESTAMP(timezone=True), nullable=True)
    effective_control_date = Column(TIMESTAMP(timezone=True), nullable=True)
    control_type = Column(String, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )
    updated_by = Column(UUID, nullable=True)
    organization_id = Column(UUID, nullable=True)
    synchronisation_id = Column(UUID, nullable=True)
