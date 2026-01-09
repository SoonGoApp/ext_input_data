from sqlalchemy import UUID, Column, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.schema import Index, UniqueConstraint

from soongo_data.sql_mappings.base import Base


class BusinessUnitsTable(Base):
    __tablename__ = 'organization_business_units'
    __table_args__ = (
        UniqueConstraint(
            'name',
            'organization_id',
            'parent_id',
            name='organization_business_units_name_organization_id_parent_id_key',
        ),
        Index('organization_business_units_created_at_idx', 'created_at'),
        Index(
            'organization_business_units_organization_id_idx',
            'organization_id'
        ),
        Index(
            'organization_business_units_original_synchronisation_id_idx',
            'original_synchronisation_id',
        ),
        Index('organization_business_units_parent_id_idx', 'parent_id'),
        Index('organization_business_units_updated_at_idx', 'updated_at'),
        {'schema': 'publ'}
    )

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
        nullable=False,
    )
    name = Column(
        Text,
        nullable=False,
    )
    organization_id = Column(
        UUID,
        ForeignKey('common.organizations.id'),
        nullable=False,
    )
    parent_id = Column(
        UUID,
        ForeignKey('publ.organization_business_units.id'),
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


class BusinessUnitConnectorIdsTable(Base):
    __tablename__ = 'business_unit_connector_ids'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4()
    )
    organization_id = Column(
        UUID,
        ForeignKey('common.organizations.id', ondelete='CASCADE'),
        nullable=False,
    )
    business_unit_id = Column(
        UUID,
        ForeignKey('publ.organization_business_units.id', ondelete='CASCADE'),
        nullable=False,
    )
    connector_id = Column(
        UUID,
        ForeignKey('common.connectors.id', ondelete='CASCADE'),
        nullable=False,
    )
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='CASCADE'),
        nullable=False,
    )
    add_params = Column(
        JSONB,
        nullable=True,
    )
    business_unit_connector_id = Column(
        Text,
        nullable=False,
    )
