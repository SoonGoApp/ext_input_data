from sqlalchemy import (TIMESTAMP, UUID, Boolean, Column, Float, ForeignKey,
                        Integer, String, func)

from soongo_data.sql_mappings.base import Base


class HotelsTable(Base):
    __tablename__ = 'hotels'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    expense_id = Column(String)
    organization_id = Column(UUID)
    booking_date = Column(TIMESTAMP(timezone=False), nullable=False)
    billing_date = Column(TIMESTAMP(timezone=False), nullable=False)
    collaborator_id = Column(
        UUID,
        ForeignKey('publ.collaborators.id', ondelete='cascade'),
    )
    supplier = Column(String)
    room_type = Column(String)
    city_name = Column(String, nullable=False)
    country_name = Column(String, nullable=False)
    room_count = Column(Integer, nullable=False)
    night_count = Column(Integer, nullable=False)
    room_night_count = Column(Integer, nullable=False)
    price_per_room_night = Column(Float)
    amount_tax_exc = Column(Float, nullable=False)
    amount_fees = Column(Float, nullable=False)
    was_negotiated = Column(Boolean)
    approver = Column(String)
    net_amount = Column(Float)
    deductible_vat = Column(Float)
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
    )
