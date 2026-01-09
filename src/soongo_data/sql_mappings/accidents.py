"""
Define the accident table mapping and related tables
"""
from sqlalchemy import (UUID, Boolean, Column, DateTime, Float, ForeignKey,
                        Text, func)

from soongo_data.sql_mappings.base import Base


class AccidentsTable(Base):
    __tablename__ = 'accidents'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        nullable=False,
        server_default=func.uuid_generate_v4(),
    )
    organization_id = Column(
        UUID,
        ForeignKey('common.organizations.id', ondelete='cascade'),
        nullable=False,
    )
    accident_date = Column(DateTime(timezone=True), nullable=False)
    accident_ref = Column(Text, nullable=True)
    vehicle_id = Column(
        UUID,
        ForeignKey('publ.vehicles.id', ondelete='cascade'),
        nullable=True,
    )
    accident_type = Column(Text, nullable=True)
    context = Column(Text, nullable=True)
    responsibility = Column(Text, nullable=True)
    third_party = Column(Boolean, nullable=True)
    insurer = Column(Text, nullable=True)
    collaborator_id = Column(
        UUID,
        ForeignKey('publ.collaborators.id', ondelete='cascade'),
        nullable=True,
    )
    cost_insurer = Column(Float, nullable=True)
    cost_self_insurance = Column(Float, nullable=True)
    cost_deductible = Column(Float, nullable=True)
    was_commute = Column(Boolean, nullable=True)
    weekend_accident = Column(Boolean, nullable=True)
    accident_location = Column(Text, nullable=True)
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
        nullable=True,
    )
    insurer_status = Column(Text, nullable=True)
    garage_status = Column(Text, nullable=True)
    created_by = Column(UUID, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    opening_date = Column(DateTime(timezone=True), nullable=True)
    closing_date = Column(DateTime(timezone=True), nullable=True)
    insurer_context = Column(Text, nullable=True)
