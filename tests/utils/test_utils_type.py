import numpy as np
import pandas as pd
import pycountry
import pytest

from soongo_data.utils.type import CountryConverter

class TestUtilsType:
    def test_country_conversion_fr(self):
        converter = CountryConverter(['fr'])
        assert converter(pd.Series(['France'])).equals(pd.Series(['FRA']))
    
    def test_country_conversion_fr_lowercase(self):
        converter = CountryConverter(['fr'])
        assert converter(pd.Series(['france'])).equals(pd.Series(['FRA']))

    def test_country_conversion_fr_uppercase(self):
        converter = CountryConverter(['fr'])
        assert converter(pd.Series(['FRANCE'])).equals(pd.Series(['FRA']))

    def test_country_conversion_ch(self):
        converter = CountryConverter(['fr'])
        assert converter(pd.Series(['Suisse'])).equals(pd.Series(['CHE']))

    def test_country_conversion_ch_in_en(self):
        converter = CountryConverter(['en'])
        assert converter(pd.Series(['Switzerland'])).equals(pd.Series(['CHE']))

    def test_country_conversion_fr_and_ch(self):
        converter = CountryConverter(['fr'])
        assert converter(pd.Series(['France', 'Suisse'])).equals(pd.Series(['FRA', 'CHE']))

    def test_country_conversion_us(self):
        converter = CountryConverter(['fr'])
        assert converter(pd.Series(['États-Unis'])).equals(pd.Series(['USA']))
        assert converter(pd.Series(['etats-unis'])).equals(pd.Series(['USA']))

    def test_country_ch_french_and_english(self):
        converter = CountryConverter(['fr', 'en'])
        assert converter(pd.Series(['Switzerland', 'Suisse'])).equals(pd.Series(['CHE', 'CHE']))

    def test_country_is_nan(self):
        converter = CountryConverter(['fr', 'en'])
        assert converter(pd.Series([np.nan])).equals(pd.Series(['']))

    def test_country_doesnt_exist(self):
        with pytest.raises(KeyError) as exc_info:
            converter = CountryConverter(['fr', 'en'])
            converter(pd.Series(['Unknown Country'])).equals(pd.Series(['']))
        assert "Country name not found in mapping: 'unknown country'" in str(exc_info.value)

    def test_country_alpha2_to_alpha3(self):
        converter = CountryConverter(['fr', 'en'])
        assert converter(pd.Series(['FR'])).equals(pd.Series(['FRA']))
        assert converter(pd.Series(['fr'])).equals(pd.Series(['FRA']))

    def test_country_alpha3_to_alpha3(self):
        converter = CountryConverter(['fr'])
        assert converter(pd.Series(['FRA'])).equals(pd.Series(['FRA']))
        assert converter(pd.Series(['fra'])).equals(pd.Series(['FRA']))

    def test_france_with_space(self):
        converter = CountryConverter(['fr'])
        assert converter(pd.Series([' france'])).equals(pd.Series(['FRA']))