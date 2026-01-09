import json
import os
import typing
from unidecode import unidecode

import numpy as np
import pandas as pd
import pycountry
from babel import Locale

from soongo_data.utils.logging_utils import gen_logger


def convert_date(
    date_series: pd.Series,
    date_format: typing.Optional[str] = None,
    force_format: bool = False,
) -> pd.Series:
    """Convert date series, handling pandas base utility errors on French
        months

    :param date_series: a Series of dates as strings or integers

    :returns: Series converted to datetime
    """
    # Convert Excel style integer dates, or float for datetime
    if pd.api.types.is_numeric_dtype(date_series.dtype):
        max_int_date = date_series.loc[pd.notna(date_series)].max()
        if max_int_date < 30000:
            raise ValueError(
                'An integer series was provided for date casting, but values'
                'are not credible dates values (before 1982)'
            )
        if max_int_date > 55000:
            raise ValueError(
                'An integer series was provided for date casting, but values'
                'are not credible dates values (after 2050)'
            )

        # Reducing precision to avoid overflow errors
        if pd.api.types.is_integer_dtype(date_series.dtype):
            date_series = date_series.astype('Int32')
        elif pd.api.types.is_float_dtype(date_series.dtype):
            date_series = date_series.astype('float32')

        # 0 translates into 30/12/1899 in Excel string formatting
        return pd.to_datetime(
            date_series,
            unit='D',
            origin='1899-12-30',
        )

    # Convert stringified dates
    if date_format:
        day_first = date_format.startswith(r'%d')
        year_first = date_format.startswith(r'%Y')
    else:
        day_first = True  # Default in European data.
        year_first = False

    converted_date = pd.to_datetime(
        date_series,
        errors='coerce',
        format=date_format if force_format else 'mixed',
        dayfirst=day_first,
        yearfirst=year_first,
    )
    conversion_errors = series_is_nan(converted_date) & ~series_is_nan(
        date_series
    )
    if conversion_errors.any():
        date_logger = gen_logger('convert_date')

        date_logger.error(
            'Error in the date conversion of series %s for %d occurences out '
            'of %d trying to parse with dateparser for values: %s',
            date_series.name,
            conversion_errors.sum(),
            date_series.shape[0],
            date_series.loc[conversion_errors].unique(),
        )

    return converted_date


def convert_numeric(str_series: pd.Series, decimal: str = ',') -> pd.Series:
    """Convert a string numeric value series to float

    :param str_series: a Series of dates as strings

    :returns: Series converted to datetime
    """
    if pd.api.types.is_numeric_dtype(str_series.dtype):
        return str_series

    if decimal != '.':
        str_series = str_series.astype(str).str.replace(decimal, '.')
    else:
        str_series = str_series.astype(str).str.replace(',', '')
    for charac in [
        ' ',
        '€',
        'TTC',
        'HT',
        'km',
        'ans',
        'an',
        '(valeurcalculée)',
        '\x80',
        "'",
        '\xa0',
    ]:
        str_series = str_series.astype(str).str.replace(charac, '')

    lost_values = str_series.loc[
        pd.isna(pd.to_numeric(str_series, errors='coerce'))
    ]
    if lost_values.any():
        # Create console handler and set level to debug
        method_logger = gen_logger('convert_numeric')
        method_logger.debug(
            f'Lost {len(lost_values)} in processing {str_series.name}: '
            f'{lost_values.unique()}'
        )

    return pd.to_numeric(str_series, errors='coerce')


class FloatToStrIntConverter:
    """Convert a float series to a string of integers, with a specified
    decimal separator and a specified length to pad
    """

    def __init__(
        self,
        decimal: str,
        thousands: str = '',
        str_unit: typing.Optional[str] = None,
        required_length: int = 0,
    ):
        self.numeric_converter = NumericConverter(
            decimal=decimal,
            thousands=thousands,
            str_unit=str_unit,
        )
        self.required_length = required_length

    def __call__(self, float_series: pd.Series) -> pd.Series:
        float_series = self.numeric_converter(float_series).astype('Int64')
        float_series = float_series.astype('string')
        if self.required_length:
            float_series = float_series.str.zfill(self.required_length)
        return float_series


def convert_boolean(
    str_series: pd.Series,
    pos_value: str = 'oui',
    neg_value: str = 'non',
) -> pd.Series:
    """Convert a string boolean value series to boolean

    :param str_series: a string series with oui/non values

    :raises ValueError: if series contains others that oui/non/nan

    :returns: Series converted to boolean
    """
    if pd.api.types.is_integer_dtype(str_series.dtype):
        unique_values = str_series.unique()
        if not set(unique_values) == {0, 1}:
            raise ValueError(
                f'Integer series can only be converted to boolean if 0/1 '
                f'valued, but contains: {unique_values}'
            )
        return str_series.map({0: False, 1: True})

    series_values = str_series[~series_is_nan(str_series)].str.lower().unique()
    if not set(series_values).issubset({pos_value, neg_value}):
        raise ValueError(
            f'This processing is only suitable for {pos_value}/{neg_value} '
            f'encoded columns but series contains {series_values}'
        )
    str_series = str_series.str.lower().str.strip()
    bool_series = np.where(
        str_series.str.lower() == pos_value,
        True,
        False,
    )
    return bool_series


def convert_string(str_series: pd.Series) -> pd.Series:
    """Convert a string series to a string, filling Nan values

    :param str_series: a string series

    :returns: Series converted to string with nan replaced as ''
    """
    return str_series.fillna('').astype('string').str.strip()


def clean_accent(str_series: pd.Series):
    """Clean Pandas string series withdrawing accents and capitalization"""
    str_series = str_series.str.replace('-', ' ')
    str_series = str_series.str.normalize('NFKD')
    return str_series.str.encode('ascii', 'ignore').str.decode('utf-8')


def update_names_conversion_dict(
    names_series: pd.Series,
    organization_name: str,
):
    """Update the names correction dictionary with the names in the series

    :param names_series: a series of names
    :param organization_name: the name of the organization
    """
    names_series = clean_accent(convert_string(names_series)).str.lower()
    names_series = names_series.str.replace(',', '')
    names_series = names_series.apply(gen_name_set)
    with open(
        os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                'names_correction.json',
            )
        )
    ) as correction_file:
        name_dict = json.load(correction_file)

    for name in names_series:
        if organization_name in name_dict:
            org_dict = name_dict[organization_name]
            assert 'names' in org_dict, (
                'Error in the names correction dictionary - should have'
                'names and params keys for each organization'
            )
            if name not in org_dict['names']:
                name_dict[organization_name]['names'][name] = name

    with open(
        os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                'names_correction.json',
            )
        ),
        'w',
    ) as correction_file:
        json.dump(name_dict, correction_file, indent=4)


class NamesConverter:
    """Convert a string series to a string of names, deleting accent et al

    :param str_series: a string series

    :returns Series converted to a string without accent and lowercase
    """

    def __init__(self, organization_name: str):
        with open(
            os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__),
                    'names_correction.json',
                )
            )
        ) as correction_file:
            org_dict = json.load(correction_file)
            assert organization_name in org_dict, (
                f'Error in the names correction dictionary - organization '
                f'{organization_name} not found'
            )
            org_dict = org_dict[organization_name]
            assert 'names' in org_dict, (
                'Error in the names correction dictionary - should have'
                'names and params keys for each organization'
            )
            self.name_dict = org_dict['names']
            self.enforce = org_dict.get('params', {}).get('enforce', False)

        corrections = {
            orig_name: correct_name
            for orig_name, correct_name in self.name_dict.items()
            if orig_name != correct_name
        }
        overlap = set(corrections.keys()).intersection(
            set(corrections.values())
        )
        assert overlap == set(), (
            f'Error names correction dictionary '
            f'- overlap between keys: {overlap}'
        )

    def __call__(self, series: pd.Series) -> pd.Series:
        series = clean_accent(convert_string(series)).str.lower()
        series = series.str.replace(',', '')
        series = series.apply(gen_name_set)
        substitute = series.map(self.name_dict)
        if self.enforce:
            return substitute
        return series.mask(pd.notna(substitute), substitute)


def gen_name_set(full_name: str) -> str:
    """Gen name set, an order string with the set of words in the name.

    :param full_name: a string name

    :return: a string with all words in the name ordered alphabetically
    """
    if not isinstance(full_name, str):
        return ''

    ordered_names = full_name.split()
    ordered_names.sort()

    return ' '.join(ordered_names)


class PlateConverter:
    def __init__(self: typing.Self, org_slug: str, raise_errors: bool = False):
        """Initialize the plate converter

        :param raise_errors: whether to raise errors if the plate format is not
            correct
        """
        self.raise_errors = raise_errors
        self.logger = gen_logger('plate_correction')
        correction_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                'plate_correction.json',
            )
        )
        with open(correction_path) as correction_file:
            org_dict = json.load(correction_file)
            if org_slug not in org_dict:
                self.logger.info(
                    'No entry for org %s in plate_dict; no correcting plates'
                )
                self.plate_mapping = {}
            else:
                self.plate_mapping = org_dict[org_slug]

    def __call__(self: typing.Self, plates_series: pd.Series) -> pd.Series:
        plates_series = convert_plate(plates_series, self.raise_errors)
        corrected_plates = plates_series.map(self.plate_mapping)
        return plates_series.mask(
            pd.notna(corrected_plates),
            corrected_plates,
        )


def convert_plate(
    str_series: pd.Series, raise_errors: bool = True
) -> pd.Series:
    """Convert a string series to a string of plates, in the format XX-123-XX
    :param str_series: a string series
    :param raise_errors: whether to raise errors if the plate format is not
        correct
    :returns Series converted to a string without accent and lowercase
    """
    str_series = convert_string(str_series).fillna('')
    str_series = str_series.str.replace("'", '')
    str_series = str_series.str.replace("_", '-')
    str_series = str_series.str.replace(' ', '')
    format_match = str_series.str.match(
        pat=r'^(?:VEC)?[a-z]{2}(?: |–|-)?\d{3}(?: |–|-)?[a-z]{2}',
        case=False,
    )
    already_valid = str_series.str.match(
        pat=r'^[a-z]{2}-\d{3}-[a-z]{2}',
        case=False,
    )

    no_match_values = str_series.loc[
        ~format_match & ~series_is_nan(str_series) & ~already_valid
    ]
    if no_match_values.astype('object').any():
        if raise_errors:
            raise ValueError(
                f'Attempted to convert plate to format but series does not '
                f'match for example {no_match_values.unique()}'
            )
        else:
            method_logger = gen_logger('convert_plate')
            method_logger.debug(
                'Attempted to convert plate to format but series does not '
                'match for example %s',
                no_match_values.unique(),
            )

    str_series = str_series.mask(already_valid, str_series.str.upper())
    return str_series.mask(
        format_match & ~already_valid,
        str_series.str.replace(
            r'^(?:VEC)?([a-z]{2})(?: |–|-)?(\d{3})(?: |–|-)?([a-z]{2})',
            r"\1-\2-\3",
            regex=True,
            case=False,
        )
    )


def default_plate_converter(plate_series: pd.Series) -> pd.Series:
    """Convert a string series to a string of names, deleting accent et al

    :param plate_series: a string series

    :returns Series converted to a string without accent and lowercase
    """
    return convert_plate(
        convert_string(plate_series),
        raise_errors=False,
    )


def is_vin(vin_series: pd.Series) -> pd.Series:
    """Check if a series is a valid VIN number

    :param vin_series: a series of strings

    :returns: Series of boolean indicating whether the series is a valid VIN
    """
    vin_series = convert_string(vin_series)
    vin_series = vin_series.str.replace(' ', '')
    valid_vin = vin_series.str.match(
        r'^[A-HJ-NPR-Z0-9]{17}$',
        case=False,
    )
    return valid_vin


def convert_json(
    str_series: pd.Series,
) -> pd.Series:
    """
    Convert a string series to a json series

    :param str_series: a string series with json values
    """
    return str_series.apply(json.loads)


def convert_phone_number(
    str_series: pd.Series,
    errors: str = 'log',
) -> pd.Series:
    """Convert a string phone number series to a string

    :param str_series: a string series with phone numbers

    :returns: Series converted to string
    """
    assert errors in ('raise', 'drop', 'log'), (
        'Error in the errors parameter, should be either raise, drop or log'
    )
    str_series = convert_string(str_series)
    str_series = str_series.str.replace(r'\s+', '', regex=True)
    str_series = str_series.str.replace('(0)', '')
    str_series = str_series.str.replace('-', '')
    str_series = str_series.str.replace('.', '')

    # Check format
    international_format = str_series.str.match(r'^\+?\d{11,}$')
    national_missing0_format = str_series.str.match(
        r'^(?:1|2|3|4|5|6|7)\d{8}$'
    )
    national_format = str_series.str.match(r'^0(?:1|2|3|4|5|6|7)\d{8}$')
    invalid_values = str_series.loc[
        ~(
            international_format
            | national_format
            | str_is_nan(str_series)
            | national_missing0_format
        )
    ].unique()
    if invalid_values:
        if errors == 'raise':
            raise ValueError(
                f'Phone number series contains invalid values: '
                f'{invalid_values}'
            )

        method_logger = gen_logger('convert_phone_number')
        method_logger.debug(
            'Phone number series contains invalid values: %s',
            invalid_values,
        )
        if errors == 'drop':
            str_series = str_series.mask(
                ~international_format & ~national_format,
                None,
            )

    # International format
    str_series = str_series.mask(
        international_format, str_series.str.replace('+', '')
    )
    str_series = str_series.mask(
        international_format,
        (
            '+'
            + str_series.str[0:2]
            + ' '
            + str_series.str[2]
            + ' '
            + str_series.str[3:5]
            + ' '
            + str_series.str[5:7]
            + ' '
            + str_series.str[7:9]
            + ' '
            + str_series.str[9:]
        ),
    )

    # National format
    str_series = str_series.mask(
        national_format,
        (
            str_series.str[0:2]
            + ' '
            + str_series.str[2:4]
            + ' '
            + str_series.str[4:6]
            + ' '
            + str_series.str[6:8]
            + ' '
            + str_series.str[8:10]
        ),
    )
    str_series = str_series.mask(
        national_missing0_format,
        (
            '0'
            + str_series.str[0:1]
            + ' '
            + str_series.str[1:3]
            + ' '
            + str_series.str[3:5]
            + ' '
            + str_series.str[5:7]
            + ' '
            + str_series.str[7:9]
        ),
    )

    return str_series


def convert_g_to_kg(co2_series: pd.Series) -> pd.Series:
    co2_series = convert_numeric(co2_series) / 1000
    assert (co2_series.loc[pd.notna(co2_series)] < 1).all(), (
        'Error in the convertion of the co2 series, check number format'
    )
    return co2_series


def str_is_nan(
    str_series: pd.Series,
    null_values: typing.Tuple[str] = (
        '',
        'nan',
        'NaT',
        'None',
        ' ',
        '<NA>',
        '-',
    ),
) -> pd.Series:
    """Return a boolean Series indicating if the str series is Nan.

    :param str_series: Pandas Series of strings, with null values saved as
    string such as 'nan'
    :param null_values: tuple of strings accepted as null values
    """
    if not null_values:
        return str_series
    return str_series.isin(null_values) | pd.isna(str_series)


def series_is_nan(data_series: pd.Series) -> pd.Series:
    """Check whether a series is Nan, including string.

    param data_series: Pandas Series of any dtype

    :return: Series of boolean indicating whether the series is nan
    """
    col_type = data_series.dtype
    if pd.api.types.is_string_dtype(col_type) or pd.api.types.is_object_dtype(
        col_type
    ):
        return str_is_nan(data_series)

    else:
        return pd.isna(data_series)


def scalar_is_nan(scalar: typing.Any) -> bool:
    """Check whether scalar is Nan, including string.

    :param scalar: Any scalar value

    :return: boolean indicating whether the scalar is nan
    """
    if isinstance(scalar, str):
        return scalar in ('', 'nan', 'NaT', 'None', ' ', '<NA>', '-')

    return pd.isna(scalar)


def df_is_nan(df: pd.DataFrame) -> pd.DataFrame:
    """Check whether each element in a DataFrame is Nan, including string.

    :param data_series: Pandas Series of any dtype

    :return: Series of boolean indicating whether the series is nan
    """
    output_lst = []
    for col in df.columns:
        output_lst.append(series_is_nan(df[col]))

    return pd.concat(output_lst, axis=1)


def map_dtype_to_scalar_type(dtype: str) -> typing.Type:
    """Map pandas dtype to scalar types

    :param dtype: pandas dtype string name

    :returns: equivalent ScalarType, see below, typing.Optional used for nulla
    ble types

    https://pandas.pydata.org/pandas-docs/stable/user_guide/basics.html#basics-dtypes
    """
    _map_dict = {
        'category': str,
        'string': str,
        'bool': typing.Optional[bool],
    }
    map_match = _map_dict.get(dtype)
    if map_match:
        return map_match

    if pd.api.types.is_datetime64_any_dtype(dtype):
        return pd.Timestamp

    if isinstance(dtype, pd.IntervalDtype):
        return pd.Interval

    if isinstance(dtype, pd.Period):
        return pd.Period

    if pd.api.types.is_integer_dtype(dtype):
        return typing.Optional[int]

    if pd.api.types.is_float_dtype(dtype):
        return typing.Optional[float]

    # If object does not match any
    return typing.Any


def get_dtype_null(dtype: str):
    """Returns the null value corresponding to the specified pandas dtype"""
    if pd.api.types.is_datetime64_any_dtype(
        dtype
    ) or pd.api.types.is_timedelta64_dtype(dtype):
        return pd.NaT
    if pd.api.types.is_any_real_numeric_dtype(dtype):
        return np.nan
    if (dtype == 'Interval') or pd.api.types.is_bool_dtype(dtype):
        return pd.NA
    if (
        pd.api.types.is_string_dtype(dtype)
        or pd.api.types.is_object_dtype(dtype)
        or isinstance(dtype, pd.api.types.CategoricalDtype)
    ):
        return ''
    else:
        raise TypeError(
            f'Dtype {dtype} not handled by the return filler function'
        )


def convert_0_to_nan(series):
    return series.mask(
        np.isclose(pd.to_numeric(series), 0),
        np.nan,
    )


def remover_tz_from_iso8601(str_series: pd.Series) -> pd.Series:
    return pd.to_datetime(str_series, format='ISO8601').dt.tz_localize(None)


class DateConverter:
    def __init__(
        self,
        date_format: str,
        force_format: bool = False,
        drop_tz: bool = True
    ):
        self.date_format = date_format
        self.force_format = force_format
        self.drop_tz = drop_tz

    def __call__(self, str_series: pd.Series):
        date_series = convert_date(
            convert_string(str_series),
            date_format=self.date_format,
            force_format=self.force_format,
        )
        if self.drop_tz:
            date_series = date_series.dt.tz_localize(None)

        return date_series


class BooleanConverter:
    def __init__(self, pos_value: str, neg_value: str):
        self.pos_value = pos_value
        self.neg_value = neg_value

    def __call__(self, str_series: pd.Series):
        return convert_boolean(
            convert_string(str_series),
            pos_value=self.pos_value,
            neg_value=self.neg_value,
        )


class NumericConverter:
    def __init__(
        self,
        decimal: str,
        thousands: str = '',
        str_unit: typing.Optional[str] = None,
    ) -> None:
        self.decimal = decimal
        self.thousands = thousands
        self.str_unit = str_unit

    def __call__(self, str_series: pd.Series):
        cleaned_series = convert_string(str_series).str.replace(
            self.thousands, ''
        )
        if self.str_unit:
            cleaned_series = cleaned_series.str.replace(self.str_unit, '')
        return convert_numeric(
            cleaned_series,
            decimal=self.decimal,
        )


class JsonConverter:
    def __init__(
        self: typing.Self,
        key: str,
        extra_args: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ):
        self.extra_args = extra_args or {}
        self.key = key

    def __call__(self, str_series: pd.Series):
        return str_series.apply(
            lambda x: json.dumps({self.key: x, **self.extra_args})
        )


class DictColumnGetter:
    def __init__(self, keys: typing.Tuple[str]):
        self.keys = keys

    def __call__(self, str_series: pd.Series) -> pd.Series:
        return str_series.apply(self.literal_get)

    def literal_get(
        self: typing.Self, str_dict: typing.Union[str, dict]
    ) -> dict:
        if isinstance(str_dict, dict):
            value = str_dict
        elif not str_is_nan(pd.Series([str_dict])).any():
            try:
                value = json.loads(str_dict)
                assert isinstance(value, dict)
            except Exception:
                raise ValueError(
                    f'Error in the conversion of the dict column, expected '
                    f'dict but got {str_dict}'
                )
        else:
            return None

        for key in self.keys:
            value = value.get(key) if value else None

        return value


class IntToFloatConverter:
    def __init__(self, nb_decimal: int = 0) -> None:
        assert nb_decimal >= 0, 'Number of decimal must be positive'
        self.nb_decimal = nb_decimal

    def __call__(self, x: str) -> typing.Optional[float]:
        numeric = convert_numeric(
            convert_string(x).replace('+', ''),
        )

        return numeric / 10**self.nb_decimal


class VinConverter:

    def __init__(self, raise_invalid: bool = False):
        self.raise_invalid = raise_invalid

    def __call__(self, vin_series: pd.Series) -> pd.Series:
        """Convert a string series to a string of VINs, in uppercase without
        spaces

        :param vin_series: a string series

        :returns Series converted to a string without accent and lowercase
        """
        vin_series = convert_string(vin_series).str.strip().str.replace(' ', '')
        vin_series = vin_series.str.upper()

        invalid_vins = ~is_vin(vin_series) & ~series_is_nan(vin_series)
        if self.raise_invalid and invalid_vins.shape[0] > 0:
            raise ValueError(
                f'VIN conversion: {invalid_vins.shape[0]} invalid VINs found out '
                f'of {vin_series.shape[0]} values: {invalid_vins.unique()}'
            )
        elif invalid_vins.shape[0] > 0:
            logger = gen_logger('vin_converter')
            logger.info(
                'VIN conversion: %d invalid VINs found out of %d values: %s',
                invalid_vins.shape[0],
                vin_series.shape[0],
                invalid_vins.unique(),
            )
            vin_series = vin_series.mask(invalid_vins)

        return vin_series


def series_equal(
    series_a: pd.Series,
    series_b: pd.Series,
    time_tolerance: pd.Timedelta | None = None,
) -> pd.Series:
    """Tests whether two series are equal, with a time tolerance for
    datetime series and using np.isclose for numeric series.
    :param series_a: first series to compare
    :param series_b: second series to compare
    :param time_tolerance: time tolerance for datetime series

    raises ValueError: if the two series have different shapes or indices

    :return: Series of boolean indicating whether the two series are equal
    """
    if time_tolerance is None:
        time_tolerance = pd.Timedelta(days=1)
    if series_a.shape != series_b.shape:
        raise ValueError(
            f'Series have different shapes: {series_a.shape} and '
            f'{series_b.shape}'
        )
    if (series_a.index != series_b.index).any():
        raise ValueError(
            'Series have different indices, cannot compare them directly'
        )

    if (
        series_a.dtype == 'datetime64[ns]'
        and series_b.dtype == 'datetime64[ns]'
    ):
        # Compare datetime series with time tolerance
        return (series_a - series_b).abs() <= time_tolerance
    elif pd.api.types.is_numeric_dtype(
        series_a
    ) and pd.api.types.is_numeric_dtype(series_b):
        # Compare numeric series using np.isclose
        return pd.Series(
            np.isclose(series_a, series_b, equal_nan=True), series_a.index
        )
    else:
        # Default comparison for other types
        return series_a == series_b


class CountryConverter:
    def __init__(
        self: typing.Self,
        country_codes: typing.List[str],
    ):
        locales = [Locale(country_code) for country_code in country_codes]

        self.name_to_country = {
            unidecode(locale.territories.get(country.alpha_2)).lower(): country.alpha_3
            for locale in locales
            for country in pycountry.countries
            if locale.territories.get(country.alpha_2)
        }

        self.name_to_country |= {
            country.alpha_2.lower(): country.alpha_3
            for country in pycountry.countries
        }

        self.name_to_country |= {
            country.alpha_3.lower(): country.alpha_3
            for country in pycountry.countries
        }

    def __call__(self: typing.Self, str_series: pd.Series):
        try:
            return str_series.fillna('').apply(
                lambda x: str() if x==str() else self.name_to_country[unidecode(x).lower().strip()]
            )
        except KeyError as e:
            raise KeyError(
                f'Country name not found in mapping: {e}'
            ) from e

    @property
    def country_mapping(self: typing.Self) -> typing.Dict[str, str]:
        return self.name_to_country
