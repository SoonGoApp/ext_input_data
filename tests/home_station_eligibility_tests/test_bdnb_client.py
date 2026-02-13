"""
Tests unitaires simples pour bdnb_client.py
"""

import pytest
from unittest.mock import patch, Mock
from infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.bdnb_client import (
    get_cle_interop_adr,
    get_building_usage
)


class TestGetCleInteropAdr:
    """Tests pour get_cle_interop_adr"""

    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.bdnb_client.requests.get')
    def test_success(self, mock_get):
        """Test cas nominal avec résultat"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "features": [{"properties": {"id": "75102_0001_00010"}}]
        }
        mock_get.return_value = mock_response

        result = get_cle_interop_adr("10 Rue de la Paix, Paris")

        assert result == "75102_0001_00010"

    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.bdnb_client.requests.get')
    def test_no_results(self, mock_get):
        """Test quand aucun résultat trouvé"""
        mock_response = Mock()
        mock_response.json.return_value = {"features": []}
        mock_get.return_value = mock_response

        result = get_cle_interop_adr("Adresse inexistante")

        assert result is None

    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.bdnb_client.requests.get')
    def test_exception(self, mock_get):
        """Test en cas d'erreur"""
        mock_get.side_effect = Exception("Network error")

        result = get_cle_interop_adr("10 Rue de la Paix, Paris")

        assert result is None


class TestGetBuildingUsage:
    """Tests pour get_building_usage"""

    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.bdnb_client.requests.get')
    def test_success(self, mock_get):
        """Test cas nominal avec usage trouvé"""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"usage_principal_bdnb_open": "habitation"}
        ]
        mock_get.return_value = mock_response

        result = get_building_usage("75102_0001_00010")

        assert result == "habitation"

    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.bdnb_client.requests.get')
    def test_no_data(self, mock_get):
        """Test quand aucune donnée trouvée"""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = get_building_usage("cle_invalide")

        assert result is None

    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.bdnb_client.requests.get')
    def test_exception(self, mock_get):
        """Test en cas d'erreur"""
        mock_get.side_effect = Exception("Network error")

        result = get_building_usage("75102_0001_00010")

        assert result is None