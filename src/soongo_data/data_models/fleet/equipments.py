
""" Equipments

Defines columns used across all Gac datasets
"""
from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.enums import (EquipmentCategories, EquipmentStatus,
                                     EquipmentTypes, FuelTypes, GazStationType,
                                     Suppliers, mapper_factory)
from soongo_data.utils.type import (convert_boolean, convert_date,
                                    convert_string)


class EquipmentsModel(BaseModel):
    gaz_station = DataColumn(
        raw_name="Site : Libellé",
        name="gaz_station",
        dtype='string',
    )
    gaz_station_ref = DataColumn(
        raw_name="Site : Code site",
        name="gaz_station_ref",
        dtype='string',
        post_processing=convert_string,
    )
    equipment_supplier: DataColumn = DataColumn(
        raw_name='Fournisseur de carte carburant',
        dtype='string',
        post_processing=mapper_factory(Suppliers),
        name='equipment_supplier',
    )
    equipment_id: DataColumn = DataColumn(
        raw_name='equipment_id',
        dtype='string',
        post_processing=convert_string,
        name='equipment_id',
        description='Soongo internal db uuid',
    )
    equipment_reference: DataColumn = DataColumn(
        raw_name='Référence de la carte',
        dtype='string',
        post_processing=convert_string,
        name='equipment_reference',
    )
    ticket_number: DataColumn = DataColumn(
        raw_name='N° Ticket',
        dtype='string',
        post_processing=convert_string,
        name='ticket_number',
    )
    card_product: DataColumn = DataColumn(
        raw_name='Produit de la carte',
        dtype='string',
        post_processing=convert_string,
        name='card_product',
    )
    fuel_type: DataColumn = DataColumn(
        raw_name='Produit',
        dtype='string',
        name='fuel_type',
        post_processing=mapper_factory(FuelTypes)
    )
    secret_code_type = DataColumn(
        raw_name='Type de code confidentiel',
        dtype='string',
        post_processing=convert_string,
        name='secret_code_type',
    )
    equipment_code = DataColumn(
        raw_name='Code confidentiel',
        dtype="string",
        name='equipment_code',
    )
    driver_code = DataColumn(
        raw_name='Code chauffeur',
        dtype='string',
        post_processing=convert_string,
        name='driver_code',
    )
    equipment_start_date = DataColumn(
        raw_name='equipment_start_date',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='equipment_start_date',
    )
    equipment_status_date = DataColumn(
        raw_name="Date d'effet",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='equipment_status_date',
    )
    equipment_status = DataColumn(
        raw_name='Statut',
        dtype='string',
        post_processing=mapper_factory(EquipmentStatus),
        name='equipment_status',
    )
    creation_date: DataColumn = DataColumn(
        raw_name="Création du support",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='creation_date',
    )
    update_date: DataColumn = DataColumn(
        raw_name='Date de màj',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='update_date',
    )
    gaz_station_type: DataColumn = DataColumn(
        raw_name='Site : Type du site',
        dtype='string',
        post_processing=mapper_factory(GazStationType),
        name='gaz_station_type',
    )
    was_approved: DataColumn = DataColumn(
        raw_name='Code réponse',
        dtype='string',
        post_processing=lambda x: convert_boolean(
            x,
            pos_value="acceptée",
            neg_value="refusée",
        ),
        name='was_approved',
    )
    approval_type: DataColumn = DataColumn(
        raw_name="Motif d'autorisation",
        dtype='string',
        post_processing=convert_string,
        name='approval_type',
    )
    equipment_category: DataColumn = DataColumn(
        raw_name='equipment_category',
        dtype='string',
        post_processing=mapper_factory(EquipmentCategories),
        name='equipment_category',
    )
    equipment_family = DataColumn(
        raw_name="Famille d'équipement",
        dtype='string',
        post_processing=convert_string,
        name='equipment_family'
    )
    equipment_product = DataColumn(
        raw_name="Type d'équipement",
        dtype='string',
        post_processing=convert_string,
        name='equipment_product'
    )
    equipment_type = DataColumn(
        raw_name="Type d'équipement",
        dtype='string',
        post_processing=mapper_factory(EquipmentTypes),
        name='equipment_type'
    )
    equipment_name = DataColumn(
        raw_name="Libellé",
        dtype='string',
        post_processing=convert_string,
        name='equipment_name'
    )
    internal_reference = DataColumn(
        raw_name="Référence interne",
        dtype='string',
        post_processing=convert_string,
        name='internal_reference'
    )
    supplier_reference = DataColumn(
        raw_name='Référence fournisseur',
        dtype='string',
        post_processing=convert_string,
        name='supplier_reference'
    )
    equipment_start_date = DataColumn(
        raw_name='Date de début',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='equipment_start_date',
    )
    equipment_end_date = DataColumn(
        raw_name='Date de fin',
        dtype='datetime64[ns]',
        name='equipment_end_date',
    )
    comment_1: DataColumn = DataColumn(
        raw_name='Commentaire (Equipement)',
        dtype='string',
        post_processing=convert_string,
        name='comment_1',
    )
    comment_2: DataColumn = DataColumn(
        raw_name='Mention supplémentaire',
        dtype='string',
        post_processing=convert_string,
        name='comment_2',
    )
    comment_3: DataColumn = DataColumn(
        raw_name='Mention Complémentaire',
        dtype='string',
        post_processing=convert_string,
        name='comment_3',
    )
