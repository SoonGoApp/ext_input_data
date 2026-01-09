from sqlalchemy import TIMESTAMP, UUID, Column, ForeignKey, String, func

from soongo_data.sql_mappings.base import Base


class EquipmentCategoryTable(Base):
    __tablename__ = 'equipment_categories'
    __table_args__ = {'schema': 'publ'}

    type = Column(String, primary_key=True, nullable=False)
    description = Column(String, nullable=True)


class EquipmentStatusTable(Base):
    __tablename__ = 'equipment_status'
    __table_args__ = {'schema': 'publ'}

    type = Column(String, primary_key=True, nullable=False)
    description = Column(String, nullable=True)


class EquipmentTable(Base):
    __tablename__ = 'equipments'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
        nullable=False,
    )
    equipment_reference = Column(String, nullable=False)
    equipment_status = Column(String, nullable=False)
    supplier_id = Column(UUID, ForeignKey('common.suppliers.id'), nullable=True)
    equipment_start_date = Column(TIMESTAMP(timezone=True), nullable=True)
    equipment_end_date = Column(TIMESTAMP(timezone=True), nullable=True)
    equipment_code = Column(String, nullable=True)
    vehicle_id = Column(UUID, ForeignKey('publ.vehicles.id'), nullable=True)
    collaborator_id = Column(
        UUID,
        ForeignKey('publ.collaborators.id'),
        nullable=True,
    )
    business_unit_id = Column(
        UUID,
        ForeignKey('publ.organization_business_units.id'),
        nullable=True,
    )
    organization_id = Column(
        UUID,
        ForeignKey('common.organizations.id'),
        nullable=False,
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default='now()',
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default='now()',
    )
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
    )
    product = Column(String, nullable=True)
    type = Column(String, nullable=True)


class EquipmentCategoriesAssignmentTable(Base):
    __tablename__ = 'equipment_categories_assignment'
    __table_args__ = {'schema': 'publ'}

    id = Column(
        UUID,
        primary_key=True,
        server_default=func.uuid_generate_v4(),
        nullable=False,
    )
    equipment_id = Column(
        UUID,
        ForeignKey('publ.equipments.id'),
        nullable=False,
    )
    equipment_category = Column(
        String,
        ForeignKey('publ.equipment_categories.type'),
        nullable=False,
    )
    synchronisation_id = Column(
        UUID,
        ForeignKey('common.synchronisations.id', ondelete='cascade'),
    )
    organization_id = Column(
        UUID,
        ForeignKey('common.organizations.id'),
        nullable=False,
    )
