import pytest
from unittest.mock import MagicMock

from soongo_data.connectors.mercedes_benz.api import MercedesBenzApiData, MercedesBenzFleetSource
from soongo_data.utils.enums import SynchronizationTypes

@pytest.fixture
def mock_logger():
    return MagicMock()

@pytest.fixture
def mock_get_local_secret(monkeypatch):
    def fake_get_local_secret(logger, organization_name=None):
        return {
            "ACORUS_MERCEDES_BENZ_CLIENT_ID": "fake_client_id",
            "ACORUS_MERCEDES_BENZ_CLIENT_SECRET": "fake_client_secret",
            "ACORUS_MERCEDES_BENZ_KAFKA_TOPIC": "fake_topic",
            "ACORUS_MERCEDES_BENZ_KAFKA_GROUP": "fake_group",
        }
    monkeypatch.setattr(
        "soongo_data.connectors.mercedes_benz.api.get_local_secret",
        fake_get_local_secret,
    )
    return fake_get_local_secret

class TestConnectorsMercedesBenzApi:
    def tests_connectors_mercedes_benz_connector_name(self, mock_logger, mock_get_local_secret):
        mercedes = MercedesBenzApiData('connector_folder_test', mock_logger, 'acorus')
        assert mercedes.CONNECTOR_NAME == 'MERCEDES_BENZ'
        assert mercedes.NAME == 'API'
        assert mercedes.TYPE == SynchronizationTypes.api.value
    
    def tests_connectors_mercedes_benz_config_init(self, mock_logger, mock_get_local_secret):
        connector_params = {}

        mercedes = MercedesBenzApiData(connector_folder="connector_folder_test", logger=mock_logger, organization_name="acorus", connector_params=connector_params)
        assert mercedes.connector_params['scope'] == 'openid groups profile audience:server:client_id:95B37AC2-D501-4CFD-B853-7D299DD2D872'
        assert mercedes.connector_params['oauth_token_api_url'] == 'https://ssoalpha.dvb.corpinter.net/v1/token'
        assert mercedes.connector_params['client_id'] == 'fake_client_id'
        assert mercedes.connector_params['client_secret'] == 'fake_client_secret'
        assert mercedes.connector_params['topic'] == 'fake_topic'
        assert mercedes.connector_params['group'] == 'fake_group'
    
    def test_connectors_mercedes_benz_api_data_source(self, mock_logger, mock_get_local_secret):
        mercedes = MercedesBenzApiData('connector_folder_test', mock_logger, 'acorus')
        assert mercedes.FLEET == MercedesBenzFleetSource

    def test_connectors_mercedes_benz_api_fleet_source_constant(self, mock_logger, mock_get_local_secret):
        mercedes_source = MercedesBenzFleetSource('test_folder', mock_logger, 'acorus')
        assert mercedes_source.NAME == 'FLEET'
        assert mercedes_source.DATASET_NAME == 'API'
        assert mercedes_source.DATASET_TYPE == SynchronizationTypes.api.value
        assert mercedes_source.CONNECTOR_NAME == 'MERCEDES_BENZ'

    def test_connectors_mercedes_benz_api_fleet_source_fetch(self, mock_logger, mock_get_local_secret):
        mercedes_source = MercedesBenzFleetSource('test_folder', mock_logger, 'acorus')
        assert 'bootstrap.streaming.connect-business.net:443' in mercedes_source.__fetch__()