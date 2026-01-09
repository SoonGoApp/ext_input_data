""" Vehicle Orders

Defines columns used across all Gac datasets
"""
from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.type import convert_date, convert_string


class VehicleOrdersModel(BaseModel):
    order_reference: DataColumn = DataColumn(
        raw_name='Référence de commande',
        dtype='string',
        post_processing=convert_string,
        name='order_reference',
    )
    buyer_name: DataColumn = DataColumn(
        raw_name="Créé par",
        dtype='string',
        post_processing=convert_string,
        name='buyer_name',
    )
    order_status_date: DataColumn = DataColumn(
        raw_name="Date d'effet",
        dtype='string',
        post_processing=convert_string,
        name='order_status_date',
    )
    order_status: DataColumn = DataColumn(
        raw_name="Statut actuel",
        dtype='string',
        post_processing=convert_string,
        name='order_status',
    )
    order_step: DataColumn = DataColumn(
        raw_name="Étape en cours",
        dtype='string',
        post_processing=convert_string,
        name='order_step',
    )
    order_date: DataColumn = DataColumn(
        raw_name='Contrat - Date de commande',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='order_date',
    )
    order_dealership: DataColumn = DataColumn(
        raw_name='Véhicule - Garage de commande (détails)',
        dtype='string',
        name='order_dealership',
    )
    order_delivery_place: DataColumn = DataColumn(
        raw_name='Véhicule - Lieu de livraison',
        dtype='string',
        name='order_delivery_place',
    )
    expected_delivery_date = DataColumn(
        raw_name="Date de livraison attendue",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='expected_delivery_date',
    )
    catalog = DataColumn(
        raw_name="Catalogue",
        dtype='string',
        post_processing=convert_string,
        name='catalog',
    )
