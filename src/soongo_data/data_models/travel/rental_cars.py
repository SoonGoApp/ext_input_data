
""" RentalCarsModel

Defines columns used across all fleet connectors datasets
"""
from soongo_data.data_models.base import DataColumn
from soongo_data.data_models.travel.base import TravelBaseModel
from soongo_data.utils.enums import RentalCarSegments, mapper_factory
from soongo_data.utils.type import convert_string


class RentalCarsModel(TravelBaseModel):
    car_segment = DataColumn(
        raw_name='Catégorie',
        dtype='string',
        post_processing=mapper_factory(RentalCarSegments),
        name='car_segment',
    )
    car_type = DataColumn(
        raw_name='Type',
        dtype='string',
        post_processing=convert_string,
        name='car_type',
    )
    rental_day_count = DataColumn(
        raw_name='Durée Location',
        dtype='float64',
        name='rental_day_count',
    )
    price_per_day = DataColumn(
        raw_name='Prix moyen/jour',
        dtype='float64',
        name='Prix moyen/jour',
    )
