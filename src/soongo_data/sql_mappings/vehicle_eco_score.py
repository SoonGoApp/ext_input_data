""" Vehicle eco scor eco scoree table definition and association tables """

from sqlalchemy import (TIMESTAMP, UUID, Boolean, Column, Date, Float,
                        ForeignKey, Integer, String, Text, UniqueConstraint,
                        case, func)

from soongo_data.sql_mappings.base import Base

class VehicleEcoScoreTable(Base):
    __tablename__ = 'vehicle_eco_score'
    __table_args__ = {'schema': 'publ'}
    id = Column(
        UUID,
        primary_key=True,
        nullable=False,
        server_default=func.uuid_generate_v4()
    )
    vehicle_id = Column(
        UUID,
        ForeignKey('publ.vehicles.id', ondelete='cascade'),
        nullable=True,
    )
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
        nullable=True,
    )
    date_from = Column(
        TIMESTAMP(timezone=True),
    )
    date_to = Column(
        TIMESTAMP(timezone=True),
    )
    score_type = Column(
        Text,
        ForeignKey('publ.score_type.type', ondelete='set null'),
        nullable=False,
    )
    score = Column(
        Float,
        nullable=False,
    )

class ScoreTypeTable(Base):
    __tablename__ = 'score_type'
    __table_args__ = (
        UniqueConstraint('type', name='unique_type'),
        {'schema': 'publ'}
    )

    type = Column(Text, primary_key=True)
    description = Column(Text, nullable=False)
