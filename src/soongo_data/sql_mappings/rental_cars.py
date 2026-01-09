from sqlalchemy import (TIMESTAMP, UUID, Column, Float, ForeignKey, String,
                        Text, func)

from soongo_data.sql_mappings.base import Base


class RentalCarsTable(Base):
    __tablename__ = 'rental_cars'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    expense_id = Column(String)
    organization_id = Column(UUID, nullable=False)
    booking_date = Column(TIMESTAMP(timezone=False), nullable=False)
    billing_date = Column(TIMESTAMP(timezone=False), nullable=False)
    collaborator_id = Column(
        UUID,
        ForeignKey('publ.collaborators.id', ondelete='cascade'),
    )
    supplier = Column(String, nullable=False)
    car_segment = Column(Text, nullable=False)
    car_type = Column(Text, nullable=False)
    start_city = Column(Text, nullable=False)
    start_country_name = Column(Text, nullable=False)
    arrival_city = Column(Text, nullable=False)
    arrival_country_name = Column(Text, nullable=False)
    start_datetime = Column(TIMESTAMP(timezone=True))
    end_datetime = Column(TIMESTAMP(timezone=True))
    amount_tax_exc = Column(Float, nullable=False)
    amount_fee = Column(Float, nullable=False)
    net_amount = Column(Float)
    deductible_vat = Column(Float)
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
    )
