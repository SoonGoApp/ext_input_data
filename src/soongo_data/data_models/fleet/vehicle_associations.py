""" Vehicle Associations

Defines columns used across all Gac datasets
"""
from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.enums import AssignmentType, mapper_factory
from soongo_data.utils.type import convert_date, convert_string


class VehicleAssociationsModel(BaseModel):
    previous_vehicle: DataColumn = DataColumn(
        raw_name="Véhicule précédent",
        dtype='string',
        post_processing=convert_string,
        name='previous_vehicle',
    )
    participation: DataColumn = DataColumn(
        raw_name="Participation / Redevance",
        dtype='float64',
        name='participation',
    )
    daily_participation: DataColumn = DataColumn(
        raw_name="daily_participation",
        dtype='float64',
        name='daily_participation',
    )
    association_start_date: DataColumn = DataColumn(
        raw_name="Dernier évènement : Date d'effet",
        dtype="datetime64[ns]",
        name="association_start_date",
        post_processing=lambda x: convert_date(x, date_format=r'%d/%m/%Y'),
    )
    association_end_date: DataColumn = DataColumn(
        raw_name="Dernier évènement : Date de fin",
        dtype="datetime64[ns]",
        name="association_end_date",
        post_processing=lambda x: convert_date(x, date_format=r'%d/%m/%Y'),
    )
    monthly_participation: DataColumn = DataColumn(
        raw_name="Evènement en cours : Participation / Redevance ( / mois)",
        dtype="float64",
        name="monthly_participation",
    )
    employee_attribution_date: DataColumn = DataColumn(
        raw_name="Date d'affectation au collaborateur",
        dtype="datetime64[ns]",
        name="employee_attribution_date",
        post_processing=lambda x: convert_date(x, date_format=r'%d/%m/%Y'),
    )
    assigned_service: DataColumn = DataColumn(
        raw_name='CODE SOCIETE',
        name='assigned_service',
        dtype='string',
        post_processing=convert_string,
    )
    next_vehicle_plate = DataColumn(
        raw_name='Véhicule suivant - Référence Immatriculation',
        dtype='string',
        name='next_vehicle_plate',
        post_processing=lambda x: x.replace('Réf. ', '')
    )
    monthly_ikb_value = DataColumn(
        raw_name='IKB',
        dtype='float64',
        name='ikb_value',
    )
    ikb_start_date = DataColumn(
        raw_name='IKB : Date de début',
        dtype='datetime64[ns]',
        name='ikb_start_date',
    )
    pool_vehicle = DataColumn(
        raw_name="Véhicule de Pool",
        dtype='string',
        post_processing=convert_string,
        name='pool_vehicle',
    )
    employee_or_cost_center_id = DataColumn(
        raw_name='Matricule Perm',
        name='employee_or_cost_center_id',
        dtype='string',
    )
    assignment_comment = DataColumn(
        raw_name="Données calculées > Affectation courante > Remarque",
        name="assignment_comment",
        dtype='string',
        post_processing=convert_string,
    )
    assignment_type: DataColumn = DataColumn(
        raw_name='Données calculées > Affectation courante > Type',
        name='assignment_type',
        dtype='string',
        post_processing=mapper_factory(AssignmentType),
    )
