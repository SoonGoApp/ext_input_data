"""
Define the attribution mapping and related tables
"""
from sqlalchemy import (JSON, TIMESTAMP, UUID, Boolean, Column, ForeignKey,
                        Text, func)

from soongo_data.sql_mappings.base import Base


class KpisTable(Base):
    __tablename__ = 'kpis'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    display_name = Column(
        Text,
        nullable=False,
    )
    description = Column(Text)
    is_active = Column(
        Boolean,
        nullable=False,
        server_default='false',
    )
    unit = Column(Text)
    kpi_category_id = Column(
        UUID,
        ForeignKey('publ.kpi_categories.id', ondelete='CASCADE'),
        nullable=False,
    )
    formula = Column(
        JSON,
        nullable=False,
        server_default='{"left": {"type": "constant-primitive", "value": 1}}'
    )
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
    bundled_kpi = Column(Boolean, server_default='false')


class KpiCategoryTable(Base):
    __tablename__ = 'kpi_categories'
    __table_args__ = (
        {
            'schema': 'publ',
        }
    )

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    display_name = Column(
        Text,
        nullable=False,
        index=True,
    )
    description = Column(Text)
    parent_id = Column(
        UUID,
        ForeignKey('publ.kpi_categories.id', ondelete='CASCADE'),
        index=True,
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


class SubKpiTable(Base):
    __tablename__ = 'kpi_sub_kpis'
    __table_args__ = (
        {
            'schema': 'publ',
        }
    )

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    kpi_id = Column(
        UUID,
        ForeignKey('publ.kpis.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    sub_kpi_id = Column(
        UUID,
        ForeignKey('publ.kpis.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
