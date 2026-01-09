""" Gac Column

Defines columns used across all Gac datasets
"""
from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.enums import MileageSourceType, mapper_factory
from soongo_data.utils.type import (convert_date, convert_numeric,
                                    convert_string)


class MileageReportsModel(BaseModel):
    mileage: DataColumn = DataColumn(
        raw_name='Km relevé',
        dtype="float64",
        name='mileage',
        post_processing=convert_numeric,
    )
    monthly_mileage: DataColumn = DataColumn(
        raw_name='Km relevé',
        dtype="Int64",
        name='monthly_mileage',
        post_processing=convert_numeric,
    )
    mileage_date: DataColumn = DataColumn(
        raw_name='Date du relevé',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='mileage_date',
    )
    mileage_month: DataColumn = DataColumn(
        raw_name='Month',
        dtype='string',
        name='mileage_month',
        post_processing=convert_string,
    )
    kilometers_driven = DataColumn(
        raw_name="Km. parcourus",
        dtype='float64',
        post_processing=convert_numeric,
        name='kilometers_driven',
    )
    mileage_source_type = DataColumn(
        raw_name='Source',
        dtype='string',
        name='mileage_source_type',
        post_processing=mapper_factory(MileageSourceType)
    )
    engine_hours = DataColumn(
        raw_name='Heures moteur',
        dtype='float64',
        name='engine_hours',
        post_processing=convert_numeric,
    )
    latest_mileage: DataColumn = DataColumn(
        raw_name='Km relevé',
        dtype='float64',
        name='latest_mileage',
        post_processing=convert_numeric,
    )
    latest_mileage_date: DataColumn = DataColumn(
        raw_name='Date du relevé',
        dtype='datetime64[ns]',
        name='latest_mileage_date',
        post_processing=convert_numeric,
    )
