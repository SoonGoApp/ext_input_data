from sqlalchemy import TIMESTAMP, UUID, Column, Float, ForeignKey, String, func

from soongo_data.sql_mappings.base import Base


# Define a table model with the specified columns
class ExpenseClaimsTable(Base):
    __tablename__ = 'expense_claims'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    expense_date = Column(TIMESTAMP, nullable=False)
    organization_id = Column(
        UUID,
        ForeignKey('common.organizations.id', ondelete='cascade'),
    )
    collaborator_id = Column(
        UUID,
        ForeignKey('publ.collaborators.id', ondelete='cascade'),
    )
    currency = Column(String, nullable=False)
    expense_type = Column(String)
    net_amount = Column(Float)
    amount_tax_exc = Column(Float)
    deductible_vat = Column(Float)
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
    )
    quantity = Column(Float)
