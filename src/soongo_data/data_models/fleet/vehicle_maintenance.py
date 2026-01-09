""" VehicleMaintenanceModel

Defines columns used across all fleet connectors datasets
"""
from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.type import (
    convert_date, convert_numeric, convert_string
)
from soongo_data.utils.enums import MaintenanceType, mapper_factory


class VehicleMaintenanceModel(BaseModel):
    maintenance_type = DataColumn(
        raw_name='Type',
        dtype='string',
        post_processing=mapper_factory(MaintenanceType),
        name='maintenance_type',
    )
    intervention_number = DataColumn(
        raw_name="N° d'intervention",
        dtype='Int64',
        name='intervention_number'
    )
    computed_service_date = DataColumn(
        raw_name='Date cible',
        dtype='datetime64[ns]',
        name='computed_service_date',
    )
    computed_service_time = DataColumn(
        raw_name='Horodatage cible',
        dtype='datetime64[ns]',
        name='computed_service_time',
    )
    computed_service_mileage = DataColumn(
        raw_name='km cible',
        dtype='float64',
        post_processing=convert_numeric,
        name='computed_service_mileage',
    )
    scheduled_service_date = DataColumn(
        raw_name='Date prévue',
        dtype='datetime64[ns]',
        name='scheduled_service_date',
    )
    effective_service_date = DataColumn(
        raw_name='Date de réalisation',
        dtype='datetime64[ns]',
        name='effective_service_date',
    )
    maintenance_date = DataColumn(
        raw_name='Réalisé le',
        dtype='datetime64[ns]',
        name='maintenance_date',
    )
    maintenance_mileage = DataColumn(
        raw_name='Réalisé à',
        dtype='Int64',
        name='maintenance_mileage',
        post_processing=convert_numeric,
    )
    last_refuel_date = DataColumn(
        raw_name='Dernier plein le',
        dtype='datetime64[ns]',
        name='last_refuel_date',
    )
    last_refuel_mileage = DataColumn(
        raw_name='Dernier plein à',
        dtype='Int64',
        name='last_refuel_mileage',
        post_processing=convert_numeric,
    )
    periodicity = DataColumn(
        raw_name='Périodicité',
        dtype='string',
        post_processing=convert_string,
        name='periodicity',
    )
    maintenance_status = DataColumn(
        raw_name='Statut',
        dtype='string',
        post_processing=convert_string,
        name='maintenance_status',
    )
    operation_description = DataColumn(
        raw_name='Description',
        dtype='string',
        post_processing=convert_string,
        name='operation_description'
    )
    maintenance_supplier = DataColumn(
        raw_name='Fournisseur',
        dtype='string',
        post_processing=convert_string,
        name='maintenance_supplier',
    )
    pollution_control_date = DataColumn(
        raw_name='Pollution',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='pollution_control_date',
    )
    computed_control_date = DataColumn(
        raw_name='Date cible',
        dtype='datetime64[ns]',
        name='computed_control_date',
    )
    computed_control_time = DataColumn(
        raw_name='Horodatage cible',
        dtype='datetime64[ns]',
        name='computed_control_time',
    )
    computed_control_mileage = DataColumn(
        raw_name='km cible',
        dtype='float64',
        post_processing=convert_numeric,
        name='computed_control_mileage',
    )
    scheduled_control_date = DataColumn(
        raw_name='Date prévue',
        dtype='datetime64[ns]',
        name='scheduled_control_date',
    )
    effective_control_date = DataColumn(
        raw_name='Date de réalisation',
        dtype='datetime64[ns]',
        name='effective_control_date',
    )
    maintenance_cost = DataColumn(
        raw_name='Coût',
        dtype='float64',
        post_processing=convert_numeric,
        name='maintenance_cost',
    )
