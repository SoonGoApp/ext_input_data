from sqlalchemy import UUID, Column, DateTime, ForeignKey, Text, func
from sqlalchemy.schema import Index, UniqueConstraint

from soongo_data.sql_mappings.base import Base


class Regions(Base):
    __tablename__ = 'organization_regions'
    __table_args__ = (
        UniqueConstraint('name', name='organization_regions_name_key'),
        Index('organization_regions_created_at_idx', 'created_at'),
        Index('organization_regions_organization_id_idx', 'organization_id'),
        Index('organization_regions_original_synchronisation_id_idx', 'original_synchronisation_id'),
        Index('organization_regions_parent_id_idx', 'parent_id'),
        Index('organization_regions_updated_at_idx', 'updated_at'),
        {'schema': 'publ'}
    )

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
        nullable=False,
    )
    name = Column(Text, nullable=False)
    organization_id = Column(
        UUID,
        ForeignKey('common.organizations.id'),
        nullable=False,
    )
    parent_id = Column(
        UUID,
        ForeignKey('publ.organization_regions.id'),
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
