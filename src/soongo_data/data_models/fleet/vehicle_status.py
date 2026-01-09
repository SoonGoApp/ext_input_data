""" Vehicle Status

Defines columns used across all Gac datasets
"""
from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.enums import VehicleStatus, mapper_factory
from soongo_data.utils.type import convert_date, convert_string


class VehicleStatusModel(BaseModel):
    vehicle_status: DataColumn = DataColumn(
        raw_name="Statut du véhicule",
        dtype='string',
        name='vehicle_status',
        post_processing=lambda x: mapper_factory(VehicleStatus)(
            x.fillna('').str.replace(
                r'\sle\s\d{1,2}\s\w*\.?\s\d{3,4}\s*',
                '',
                regex=True,
            )
        )
        # TODO: consider extracting the date information in a column
    )
    vehicle_status_start_date: DataColumn = DataColumn(
        raw_name="Date d'effet de l'évènement en cours",
        dtype='datetime64[ns]',
        name='vehicle_status_start_date',
        post_processing=convert_date,
    )
    vehicle_status_end_date: DataColumn = DataColumn(
        raw_name="Date de fin de l'évènement en cours",
        dtype='datetime64[ns]',
        name='vehicle_status_end_date',
        post_processing=convert_date,
    )
    vehicle_availability: DataColumn = DataColumn(
        raw_name="Disponibilité",
        dtype='string',
        post_processing=convert_string,
        name='vehicle_availability',
    )
    status_comment: DataColumn = DataColumn(
        raw_name="Commentaire du dernier événement",
        dtype='string',
        post_processing=convert_string,
        name='status_comment',
    )
    reason: DataColumn = DataColumn(
        raw_name="Motif",
        dtype='string',
        post_processing=convert_string,
        name='reason',
    )
    created_by: DataColumn = DataColumn(
        raw_name="Créé par",
        dtype='string',
        post_processing=convert_string,
        name='created_by',
    )
