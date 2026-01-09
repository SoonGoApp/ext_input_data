"""
Define the attribution mapping and related tables
"""
from sqlalchemy import TIMESTAMP, UUID, Column, Float, ForeignKey, func

from soongo_data.sql_mappings.base import Base


# Define a table model with the specified columns
class VehicleAttributionsTable(Base):
    __tablename__ = 'collaborators_vehicles'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    vehicle_id = Column(
        UUID,
        ForeignKey('publ.vehicles.id', ondelete='cascade'),
        nullable=False,
    )
    collaborator_id = Column(
        UUID,
        ForeignKey('publ.collaborators.id', ondelete='cascade'),
    )
    business_unit_id = Column(
        UUID,
        ForeignKey('publ.organization_business_units.id', ondelete='cascade'),
    )
    date_from = Column(TIMESTAMP(timezone=True))
    date_to = Column(TIMESTAMP(timezone=True))
    daily_participation = Column(
        Float,
        nullable=False,
        server_default='0',
    )
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
    )
