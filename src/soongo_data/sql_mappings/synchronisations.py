from sqlalchemy import (UUID, Column, DateTime, ForeignKey, Text,
                        UniqueConstraint, func)

from soongo_data.sql_mappings.base import Base


class ConnectorsTable(Base):
    __tablename__ = 'connectors'
    __table_args__ = {'schema': 'common'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
        nullable=False,
    )
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)


class SynchronisationTypesTable(Base):
    __tablename__ = 'synchronisation_types'
    __table_args__ = (
        UniqueConstraint('name', name='synchronisation_types_name_key'),
        {'schema': 'publ'}
    )

    id = Column(UUID, primary_key=True, server_default=func.uuid_generate_v4(), nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)


class SynchronisationStatusTable(Base):
    __tablename__ = 'synchronisation_status'
    __table_args__ = (
        UniqueConstraint('name', name='synchronisation_status_name_key'),
        {'schema': 'publ'},
    )

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
        nullable=False,
    )
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)


class SynchronisationsTable(Base):
    __tablename__ = 'synchronisations'
    __table_args__ = {'schema': 'common'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
        nullable=False,
    )
    connector_id = Column(
        UUID,
        ForeignKey('common.connectors.id'),
        nullable=False,
    )
    organization_id = Column(
        UUID,
        ForeignKey('common.organizations.id'),
        nullable=True,
    )
    type_id = Column(
        UUID,
        ForeignKey('publ.synchronisation_types.id'),
        nullable=False,
    )
    status_id = Column(
        UUID,
        ForeignKey('publ.synchronisation_status.id'),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        server_default=func.current_timestamp(),
        nullable=True,
    )
