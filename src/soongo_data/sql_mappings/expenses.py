""" Expenses table definition and association tables"""

from sqlalchemy import (TIMESTAMP, UUID, Column, Float, ForeignKey, Integer,
                        PrimaryKeyConstraint, Text, func)

from soongo_data.sql_mappings.base import Base


# Define a table model with the specified columns
class ExpensesTable(Base):
    __tablename__ = 'expenses'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    organization_id = Column(
        UUID,
        ForeignKey('common.organizations.id', ondelete='cascade'),
        nullable=False,
    )
    expense_reference = Column(Text)
    supplier_id = Column(UUID, ForeignKey('common.suppliers.id'), nullable=True)
    billing_date = Column(TIMESTAMP)
    amount_tax_exc = Column(Float)
    vehicle_id = Column(
        UUID,
        ForeignKey('publ.vehicles.id', ondelete='cascade'),
    )
    vat_value = Column(Float)
    deductible_vat = Column(Float)
    collaborator_id = Column(
        UUID,
        ForeignKey('publ.collaborators.id', ondelete='cascade'),
    )
    business_unit_id = Column(UUID)
    soongo_category = Column(Text)
    net_amount = Column(Float)
    quantity = Column(Float)
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
    )
    equipment_id = Column(
        UUID,
        ForeignKey('publ.equipments.id', ondelete='set null')
    )
    billing_reference = Column(
        Text,
        nullable=True,
    )
    transaction_start_date = Column(TIMESTAMP)
    transaction_end_date = Column(TIMESTAMP)
    expense_location = Column(Text)
    product = Column(Text)
    business_unit_id = Column(
        UUID,
        ForeignKey('publ.organization_business_units.id', ondelete='cascade'),
    )
    merchant_name = Column(
        Text,
    )
    accident_id = Column(
        UUID,
        ForeignKey('publ.accidents.id', ondelete='set null')
    )
    billed_entity = Column(Text)


class ExpensePrimitiveView(Base):
    __tablename__ = 'expense_primitive_view'
    __table_args__ = (
        PrimaryKeyConstraint(
            'collaborator_id',
            'vehicle_id',
            'business_unit_id',
            'month_start',
            'soongo_category',
            'supplier_name',
            name='expense_primitive_pk',
        ),
        {'schema': 'publ'},
    )

    organization_id = Column(UUID)
    collaborator_id = Column(UUID)
    vehicle_id = Column(UUID)
    business_unit_id = Column(UUID)
    month_start = Column(TIMESTAMP, nullable=False)
    soongo_category = Column(Text, nullable=False)
    supplier_name = Column(Text)
    amount_tax_exc = Column(Float)
    deductible_vat = Column(Float)
    net_amount = Column(Float)
    quantity = Column(Float)
    co2_usage_scope_1 = Column(Float)
    co2_usage_scope_2 = Column(Float)
    co2_usage_scope_3 = Column(Float)


class ExpenseSoongoCategoryTable(Base):
    __tablename__ = 'expense_soongo_category'
    __table_args__ = {'schema': 'common'}

    type = Column(Text, nullable=False, primary_key=True)
    description = Column(Text, nullable=True)
    description_fr = Column(Text, nullable=False)


class ExpenseWithAssociations(Base):
    __tablename__ = 'expenses_with_associations'
    __table_args__ = (
        {'schema': 'publ'},
    )
    id = Column(UUID, primary_key=True)
    organization_id = Column(UUID)
    expense_reference = Column(Text)
    billing_date = Column(TIMESTAMP)
    amount_tax_exc = Column(Float)
    vat_value = Column(Float)
    deductible_vat = Column(Float)
    soongo_category = Column(Text)
    net_amount = Column(Float)
    quantity = Column(Float)
    fuel_card_ref = Column(Text)
    synchronisation_id = Column(UUID, ForeignKey('common.synchronisations.id'))
    equipment_id = Column(UUID, ForeignKey('publ.equipments.id'))
    supplier_id = Column(UUID, ForeignKey('common.suppliers.id'))
    billing_reference = Column(Text)
    expense_location = Column(Text)
    transaction_start_date = Column(TIMESTAMP)
    transaction_end_date = Column(TIMESTAMP)
    product = Column(Text)
    merchant_name = Column(Text)
    collaborator_id = Column(UUID, ForeignKey('publ.collaborators.id'))
    vehicle_id = Column(UUID, ForeignKey('publ.vehicles.id'))
    business_unit_id = Column(UUID, ForeignKey('publ.organization_business_units.id'))
    rank = Column(Integer)
