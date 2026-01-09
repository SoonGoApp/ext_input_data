from sqlalchemy import (TIMESTAMP, UUID, Column, ForeignKey, Index, Integer,
                        Text, func, VARCHAR)

from soongo_data.sql_mappings.base import Base


class DocumentsTable(Base):
    __tablename__ = 'documents'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
        nullable=False,
    )
    type = Column(
        Text,
        ForeignKey('publ.document_type.type', ondelete='SET NULL')
    )
    vehicle_id = Column(
        UUID,
        ForeignKey('publ.vehicles.id', ondelete='CASCADE')
    )
    collaborator_id = Column(
        UUID,
        ForeignKey('publ.collaborators.id', ondelete='CASCADE')
    )
    path = Column(Text, nullable=False)
    filename = Column(Text, nullable=False)
    size = Column(Integer, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    hash_content = Column(
        VARCHAR(40),
        nullable=True
    )
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
        nullable=True,
    )


class DocumentType(Base):
    __tablename__ = 'document_type'
    __table_args__ = {'schema': 'publ'}

    type = Column(Text, nullable=False, primary_key=True)
    description = Column(Text)
    category = Column(Text, nullable=False)
