""" Vehicle Eco score

Defines columns used across all fleet connectors datasets
"""

from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.enums import (ScoreType,
                                     mapper_factory)
from soongo_data.utils.type import convert_numeric

class VehicleEcoScoreModel(BaseModel):
    date_from = DataColumn(
        raw_name='startDate',
        name='date_from',
        dtype='datetime64[ns]',
    )
    date_to = DataColumn(
        raw_name='endDate',
        name='date_to',
        dtype='datetime64[ns]',
    )
    score_type: DataColumn = DataColumn(
        raw_name="scoreType",
        dtype='string',
        name='score_type',
        post_processing=mapper_factory(ScoreType),
    )
    score: DataColumn = DataColumn(
        raw_name="score",
        dtype='float64',
        name='score',
        post_processing=convert_numeric,
    )
    smooth: DataColumn = DataColumn(
        raw_name="smootherPercentage",
        dtype='float64',
        name='smooth',
        post_processing=convert_numeric,
    )
    safe: DataColumn = DataColumn(
        raw_name="safeSpeedPercentage",
        dtype='float64',
        name='safe',
        post_processing=convert_numeric,
    )
    clean: DataColumn = DataColumn(
        raw_name="cleanerPercentage",
        dtype='float64',
        name='clean',
        post_processing=convert_numeric,
    )