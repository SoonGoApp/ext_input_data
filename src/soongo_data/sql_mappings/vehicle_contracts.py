from sqlalchemy import (
    Column,
    Computed,
    Date,
    Float,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

from soongo_data.sql_mappings.base import (
    Base,
    BaseView,
)


class VehicleContractsTable(Base):
    __tablename__ = 'vehicle_contracts'
    __table_args__ = {'schema': 'publ'}

    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    vehicle_id = Column(
        UUID,
        ForeignKey('publ.vehicles.id'),
        nullable=False,
    )
    organization_id = Column(UUID, ForeignKey('common.organizations.id'))
    contract_reference = Column(Text)
    lease_start_date = Column(Date)
    lease_end_date = Column(Date)
    lease_months = Column(Integer)
    lease_mileage = Column(Integer)
    date_from = Column(TIMESTAMP(timezone=True))
    date_to = Column(TIMESTAMP(timezone=True))
    contract_type = Column(Text, ForeignKey('common.contracts_type.type'))
    supplier_id = Column(UUID, ForeignKey('common.suppliers.id'))
    financial_rent_tax_exc = Column(Float)
    maintenance_rent_tax_exc = Column(Float)
    tires_rent_tax_exc = Column(Float)
    financial_loss_rent_tax_exc = Column(Float)
    replacement_vehicle_rent_tax_exc = Column(Float)
    relay_vehicle_rent_tax_exc = Column(Float)
    insurance_rent_tax_exc = Column(Float)
    fuel_card_management_rent_tax_exc = Column(Float)
    management_fee_rent_tax_exc = Column(Float)
    assistance_rent_tax_exc = Column(Float)
    telematics_rent_tax_exc = Column(Float)
    other_rent_tax_exc = Column(Float)
    tires_contract_nb = Column(Integer)
    restitution_date = Column(Date)
    interest_rate = Column(Float)
    residual_value = Column(Float)
    resale_price = Column(Float)
    resale_date = Column(TIMESTAMP(timezone=True))
    total_rent_tax_exc = Column(
        Float,
        Computed(
            'COALESCE(financial_rent_tax_exc, 0) + COALESCE(maintenance_rent_tax_exc, 0) + COALESCE(tires_rent_tax_exc, 0) + '
            'COALESCE(financial_loss_rent_tax_exc, 0) + COALESCE(replacement_vehicle_rent_tax_exc, 0) + '
            'COALESCE(relay_vehicle_rent_tax_exc, 0) + COALESCE(insurance_rent_tax_exc, 0) + '
            'COALESCE(fuel_card_management_rent_tax_exc, 0) + COALESCE(management_fee_rent_tax_exc, 0) + '
            'COALESCE(assistance_rent_tax_exc, 0) + COALESCE(telematics_rent_tax_exc, 0) + COALESCE(other_rent_tax_exc, 0)'
        ),
    )
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id'),
        nullable=False,
    )
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    sync_key = Column(
        Text,
        nullable=False,
    )


# Define the ContractType class
class ContractType(Base):
    __tablename__ = 'contracts_type'
    __table_args__ = {'schema': 'common'}

    type = Column(Text, primary_key=True)
    description = Column(Text)


# Define the VehicleContractsRanked View
class VehicleContractsRankedView(BaseView):
    __tablename__ = 'vehicle_contracts_ranked'
    __table_args__ = {'schema': 'publ'}

    id = Column(UUID, primary_key=True)
    vehicle_id = Column(UUID, ForeignKey('publ.vehicles.id'))
    organization_id = Column(UUID, ForeignKey('common.organizations.id'))
    contracts_rank = Column(Integer)
