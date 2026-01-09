from sqlalchemy import JSON, TIMESTAMP, UUID, Column, Text, func

from soongo_data.sql_mappings.base import Base


# Define a table model with the specified columns
class OrganizationsTable(Base):
    __tablename__ = 'organizations'
    __table_args__ = {'schema': 'common'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    slug = Column(
        Text,
        nullable=False,
    )
    name = Column(
        Text,
        nullable=False,
    )
    logo_path = Column(Text)
    logo_filename = Column(Text)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class OrganizationParametersTable(Base):
    __tablename__ = 'organization_parameters'
    __table_args__ = {'schema': 'common'}

    id = Column(
        UUID, primary_key=True, nullable=False, default=func.gen_random_uuid()
    )
    organization_id = Column(UUID, nullable=False)
    business_unit_id = Column(UUID, nullable=True)
    date_from = Column(TIMESTAMP(timezone=True), nullable=True)
    date_to = Column(TIMESTAMP(timezone=True), nullable=True)
    name = Column(Text, nullable=False)
    value = Column(JSON, nullable=False)
