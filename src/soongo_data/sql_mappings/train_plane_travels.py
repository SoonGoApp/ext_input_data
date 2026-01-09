from sqlalchemy import (TIMESTAMP, UUID, Column, Float, ForeignKey, Integer,
                        String, Text, func)

from soongo_data.sql_mappings.base import Base


class TrainsPlanesTable(Base):
    __tablename__ = 'trains_planes_travel'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    leg_id = Column(String)
    organization_id = Column(UUID, nullable=False)
    expense_id = Column(String)
    travel_type = Column(Text)
    booking_date = Column(TIMESTAMP(timezone=False), nullable=False)
    billing_date = Column(TIMESTAMP(timezone=False), nullable=False)
    collaborator_id = Column(
        UUID,
        ForeignKey('publ.collaborators.id', ondelete='cascade'),
    )
    airport_tax = Column(Float, nullable=False, default=0.0)
    ticket_type = Column(Text)
    leg_number = Column(Integer, nullable=False, default=1)
    start_location_code = Column(Text)
    start_city = Column(Text, nullable=False)
    start_country_name = Column(Text, nullable=False)
    arrival_location_code = Column(Text)
    arrival_city = Column(Text, nullable=False)
    arrival_country_name = Column(Text, nullable=False)
    routing = Column(Text, nullable=False)
    transporter_name = Column(Text, nullable=False)
    supplier_alliance = Column(Text)
    cabin_class = Column(Text)
    start_datetime = Column(TIMESTAMP(timezone=True))
    end_datetime = Column(TIMESTAMP(timezone=True))
    layover_time = Column(Text)
    distance = Column(Integer)
    co2_footprint = Column(Float)
    net_amount = Column(Float)
    amount_tax_exc = Column(Float)
    deductible_vat = Column(Float)
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
    )
