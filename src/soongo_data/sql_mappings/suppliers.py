from sqlalchemy import (Boolean, Column, ForeignKey, Text, UniqueConstraint,
                        func)
from sqlalchemy.dialects.postgresql import UUID

from soongo_data.sql_mappings.base import Base


class SupplierContactsTable(Base):
    __tablename__ = 'supplier_contacts'
    __table_args__ = (
        UniqueConstraint(
            'organization_id',
            'supplier_id',
            'lastname',
            'firstname',
            'email',
            name='unique_contact',
        ),
        {'schema': 'publ'}
    )

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    organization_id = Column(
        UUID,
        ForeignKey('common.organizations.id', ondelete='CASCADE'),
    )
    supplier_id = Column(
        UUID,
        ForeignKey('common.suppliers.id', ondelete='CASCADE'),
    )
    is_primary = Column(Boolean, default=False)
    lastname = Column(Text)
    firstname = Column(Text)
    email = Column(Text)
    phone = Column(Text)
    role = Column(Text)
    address = Column(Text)
    city = Column(Text)
    postal_code = Column(Text)


class SupplierTypesTable(Base):
    __tablename__ = 'supplier_types'
    __table_args__ = (
        UniqueConstraint('type', name='unique_type'),
        {'schema': 'common'}
    )

    type = Column(Text, primary_key=True)
    description = Column(Text, nullable=False)


class SuppliersTable(Base):
    __tablename__ = 'suppliers'
    __table_args__ = (
        UniqueConstraint('name', name='unique_name'),
        {'schema': 'common'}
    )

    id = Column(UUID, primary_key=True, server_default=func.uuid_generate_v4())
    name = Column(Text, nullable=False)
    type = Column(
        Text,
        ForeignKey('common.supplier_types.type', ondelete='SET NULL'),
    )
    path = Column(Text)
    filename = Column(Text)
    original_synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='SET NULL'),
    )
