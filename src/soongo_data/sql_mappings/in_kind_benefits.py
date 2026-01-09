from sqlalchemy import Column, Numeric, TIMESTAMP, UUID, ForeignKey, String

from soongo_data.sql_mappings.base import Base


class InKindBenefitsTable(Base):
    __tablename__ = 'in_kind_benefits'
    __table_args__ = {'schema': 'publ'}

    id = Column(UUID, primary_key=True, nullable=False)
    date_from = Column(TIMESTAMP(timezone=True), nullable=False)
    date_to = Column(TIMESTAMP(timezone=True), nullable=True)
    monthly_amount = Column(Numeric(10, 2), nullable=False)
    collaborator_id = Column(
        UUID,
        ForeignKey('publ.collaborators.id', ondelete='cascade'),
        nullable=False,
    )
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
    )
    type = Column(String)
