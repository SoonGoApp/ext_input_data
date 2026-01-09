from sqlalchemy import UUID, Column, Date, Double, ForeignKey, func

from soongo_data.sql_mappings.base import Base


class TaxesTable(Base):
    __tablename__ = 'taxes'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
        nullable=False,
    )
    organization_id = Column(UUID)
    collaborator_id = Column(
        UUID,
        ForeignKey('publ.collaborators.id', ondelete='cascade'),
    )
    business_unit_id = Column(UUID)
    vehicle_id = Column(UUID)
    billing_date = Column(Date, nullable=False)
    ikb_participation = Column(Double)
    declared_non_deductible_amortization = Column(Double)
    tax_vehicle_age = Column(Double)
    tax_corporate_vehicles = Column(Double)
    tax_co2_emission = Column(Double)
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
    )
    tax_pollutant = Column(Double)
