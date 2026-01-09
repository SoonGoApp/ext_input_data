""" Collaborators table definition and association tables
"""
from sqlalchemy import (TIMESTAMP, UUID, Column, ForeignKey, String,
                        UniqueConstraint, func)
from sqlalchemy.dialects.postgresql import JSONB

from soongo_data.sql_mappings.base import Base


class CollaboratorsTable(Base):
    __tablename__ = 'collaborators'
    __table_args__ = {'schema': 'publ'}
    id = Column(
        UUID,
        primary_key=True,
        nullable=False,
        server_default=func.uuid_generate_v4()
    )
    firstname = Column(
        String,
    )
    lastname = Column(
        String,
    )
    email = Column(
        String,
    )
    phone = Column(
        String,
    )
    role = Column(
        String,
    )
    work_location = Column(
        String,
    )
    organization_collaborator_id = Column(
        String,
    )
    organization_collaborator_category = Column(
        String,
    )
    organization_id = Column(
        UUID,
        ForeignKey('common.organizations.id', ondelete="CASCADE")
    )
    business_unit_id = Column(
        UUID,
    )
    region_id = Column(
        UUID,
    )
    soongo_collab_reference = Column(
        String,
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
    )
    date_from = Column(
        TIMESTAMP(timezone=True),
    )
    date_to = Column(
        TIMESTAMP(timezone=True),
    )
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
    )
    picture_href = Column(
        String,
    )
    professional_phone_number = Column(
        String,
    )
    personal_phone_number = Column(
        String,
    )
    civility = Column(String)
    personal_address = Column(String)
    birthplace = Column(String)
    birthdate = Column(String)
    license_number = Column(String)
    license_country = Column(String)
    license_issuing_date = Column(TIMESTAMP(timezone=True))
    license_issuing_place = Column(String)
    personal_street_number = Column(String)
    personal_street_name = Column(String)
    personal_postal_code = Column(String)
    personal_city = Column(String)
    personal_country = Column(String)
    analytical_entity = Column(String)


class CollaboratorConnectorIdsTable(Base):
    __tablename__ = 'collaborator_connector_ids'
    __table_args__ = (
        UniqueConstraint(
            'collaborator_id',
            'connector_id',
            'add_params',
            name='unique_collaborator_connector',
        ),
        {'schema': 'publ'},
    )
    id = Column(
        UUID,
        primary_key=True,
        nullable=False,
        server_default=func.uuid_generate_v4(),
    )
    collaborator_id = Column(
        UUID,
        ForeignKey('publ.collaborators.id', ondelete='CASCADE'),
        nullable=False,
    )
    connector_id = Column(
        UUID,
        ForeignKey('common.connectors.id', ondelete='CASCADE'),
        nullable=False,
    )
    collaborator_connector_id = Column(String, nullable=False)
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
