"""
This module contains functions that are used to post-process the data,
specifically function not general enough to be in the type module.
"""
from __future__ import annotations

import logging
import typing

import pandas as pd

from soongo_data.utils.enums import (Makes, Models, VehicleStatus,
                                     mapper_factory)
from soongo_data.utils.type import CountryConverter, convert_string

if typing.TYPE_CHECKING:
    import pandas as pd


def convert_makes(series):
    return mapper_factory(Makes)(
        convert_string(series).str.upper()
    )


def convert_model(series):
    return mapper_factory(Models)(
        convert_string(series).str.upper()
    )


def delete_status_date(series):
    return mapper_factory(VehicleStatus)(
        series.fillna('').str.replace(
            r'\sle\s\d{1,2}\s\w*\.?\s\d{3,4}\s*',
            '',
            regex=True,
        )
    )

def match_country(logger: logging.Logger, place_series: pd.Series) -> pd.Series:
    place_series = (
        place_series.str.replace(
            '-', ' ', case=False,
        ).str.replace(
            'é', 'e',
        ).str.strip()
    )
    was_matched = pd.Series(False, index=place_series.index)
    for key, value in CountryConverter(['fr', 'en']).country_mapping.items():
        criterion = place_series.str.match(
            r'(?:.*\b|^)' + key + r'(?:\b.*|$)',
            case=False,
        ).fillna(False)
        was_matched |= criterion
        place_series = place_series.mask(
            criterion,
            value
        )
    places_not_matched = place_series[~was_matched].unique()
    logger.info(
        f"{len(places_not_matched)} Countries not matched: {places_not_matched}"
    )

    return place_series.where(was_matched, pd.NA)