from sqlalchemy import TIMESTAMP, Column, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from soongo_data.sql_mappings.base import Base


class ExternalApiCache(Base):
    __tablename__ = 'external_api_cache'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=func.gen_random_uuid(),
    )
    organization_id = Column(
        UUID,
        index=True,
    )
    url = Column(Text, nullable=False)
    result = Column(JSONB, nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )
