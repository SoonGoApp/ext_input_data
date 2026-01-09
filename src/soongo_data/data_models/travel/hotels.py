""" HotelsModel

Defines columns used across all fleet connectors datasets
"""
from soongo_data.data_models.base import DataColumn
from soongo_data.data_models.travel.base import TravelBaseModel
from soongo_data.utils.enums import RoomTypes, mapper_factory
from soongo_data.utils.type import convert_string


class HotelsModel(TravelBaseModel):
    hotel_postal_code = DataColumn(
        raw_name='Code postal Hôtel',
        dtype='string',
        post_processing=convert_string,
        name='hotel_postal_code',
    )
    hotel_phone_number = DataColumn(
        raw_name='Téléphone Hôtel',
        dtype='string',
        post_processing=convert_string,
        name='hotel_phone_number',
    )
    room_type = DataColumn(
        raw_name='Type de chambre',
        dtype='string',
        post_processing=mapper_factory(RoomTypes),
        name='room_type',
    )
    room_count = DataColumn(
        raw_name='Nb Chambres',
        dtype='string',
        post_processing=convert_string,
        name='room_count',
    )
    room_night_count = DataColumn(
        raw_name='Nb nuitées',
        dtype='string',
        post_processing=convert_string,
        name='room_night_count',
    )
    price_per_room_night = DataColumn(
        raw_name='Prix par nuitée',
        dtype='float64',
        name='price_per_room_night',
    )
    hotel_address_1 = DataColumn(
        raw_name='Adresse 1',
        dtype='string',
        post_processing=convert_string,
        name='hotel_address_1',
    )
    hotel_address_2 = DataColumn(
        raw_name='Adresse 2',
        dtype='string',
        post_processing=convert_string,
        name='hotel_address_2',
    )
    night_count = DataColumn(
        raw_name='Nb nuits',
        dtype='string',
        post_processing=convert_string,
        name='night_count',
    )
    nb_days = DataColumn(
        raw_name='Durée jours',
        name='nb_days',
        dtype='Int64',
    )
