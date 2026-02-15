import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline import (
    home_station_eligibility_pipeline,
    run_pipeline
)


@pytest.fixture
def mock_config():
    """Configuration de test"""
    return {
        "database": {"schema": "test_schema"},
        "tables": {
            "input": {"collaborators_table": "collaborators"},
            "output": {"eligibility_table": "eligibility"}
        },
        "nb_rows_to_process": None 
    }


@pytest.fixture
def sample_input_df():
    """DataFrame d'entrée de test"""
    return pd.DataFrame([
        {"id": "123e4567-e89b-12d3-a456-426614174000", "full_address": "10 RUE DE LA PAIX 75002 PARIS"},
        {"id": "223e4567-e89b-12d3-a456-426614174001", "full_address": "15 AVENUE DES CHAMPS 75008 PARIS"}
    ])


class TestHomeStationEligibilityPipeline:
    """Tests pour home_station_eligibility_pipeline"""

    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.rp.insert_collaborators_eligibility_data')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.get_building_usage')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.get_cle_interop_adr')
    def test_pipeline_success_insert(self, mock_get_cle, mock_get_usage, mock_insert, mock_config, sample_input_df):
        """Test pipeline réussi avec insertion"""
        # Arrange
        mock_get_cle.side_effect = ["75102_0001_00010", "75108_0002_00020"]
        mock_get_usage.side_effect = ["habitation", "commerce"]

        # Act
        result = home_station_eligibility_pipeline(mock_config, sample_input_df, "insert")

        # Assert
        assert len(result) == 2
        assert result.iloc[0]["collaborator_id"] == "123e4567-e89b-12d3-a456-426614174000"
        assert result.iloc[0]["cle_interop_adr"] == "75102_0001_00010"
        assert result.iloc[0]["building_usage"] == "habitation"
        assert result.iloc[0]["source"] == "BDNB"
        mock_insert.assert_called_once()

    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.rp.insert_collaborators_eligibility_data')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.get_building_usage')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.get_cle_interop_adr')
    def test_pipeline_success_update(self, mock_get_cle, mock_get_usage, mock_insert, mock_config, sample_input_df):
        """Test pipeline réussi avec update"""
        # Arrange
        mock_get_cle.side_effect = ["75102_0001_00010", "75108_0002_00020"]
        mock_get_usage.side_effect = ["habitation", "commerce"]

        # Act
        result = home_station_eligibility_pipeline(mock_config, sample_input_df, "update")

        # Assert
        assert len(result) == 2
        mock_insert.assert_called_once_with(mock_config, result, "update")

    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.rp.insert_collaborators_eligibility_data')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.get_building_usage')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.get_cle_interop_adr')
    def test_pipeline_with_null_values(self, mock_get_cle, mock_get_usage, mock_insert, mock_config, sample_input_df):
        """Test pipeline avec valeurs nulles"""
        # Arrange
        mock_get_cle.side_effect = ["75102_0001_00010", None]
        mock_get_usage.side_effect = ["habitation", None]

        # Act
        result = home_station_eligibility_pipeline(mock_config, sample_input_df, "insert")

        # Assert
        assert len(result) == 2
        assert result.iloc[1]["cle_interop_adr"] is None
        assert result.iloc[1]["building_usage"] is None

    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.rp.insert_collaborators_eligibility_data')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.get_building_usage')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.get_cle_interop_adr')
    def test_pipeline_exception_handling(self, mock_get_cle, mock_get_usage, mock_insert, mock_config, sample_input_df):
        """Test gestion des exceptions"""
        # Arrange
        mock_get_cle.side_effect = Exception("API Error")

        # Act & Assert
        with pytest.raises(Exception):
            home_station_eligibility_pipeline(mock_config, sample_input_df, "insert")

    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.rp.insert_collaborators_eligibility_data')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.get_building_usage')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.get_cle_interop_adr')
    def test_pipeline_empty_dataframe(self, mock_get_cle, mock_get_usage, mock_insert, mock_config):
        """Test avec DataFrame vide - lève une exception car dropna échoue"""
        # Arrange
        empty_df = pd.DataFrame(columns=["id", "full_address"])

        # Act & Assert - Le DataFrame vide cause une KeyError dans dropna
        with pytest.raises(Exception):
            home_station_eligibility_pipeline(mock_config, empty_df, "insert")


class TestRunPipeline:
    """Tests pour run_pipeline"""

    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.home_station_eligibility_pipeline')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.rp.get_collaborators_to_update')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.rp.get_collaborators_to_process')
    def test_run_pipeline_with_updates(self, mock_get_to_process, mock_get_to_update, mock_pipeline, mock_config):
        """Test pipeline complet avec insertions et updates"""
        # Arrange
        mock_df_insert = pd.DataFrame([{"id": "123", "full_address": "10 RUE PARIS"}])
        mock_df_update = pd.DataFrame([{"id": "456", "full_address": "20 RUE LYON"}])
        
        mock_get_to_process.return_value = mock_df_insert
        mock_get_to_update.return_value = mock_df_update

        # Act
        run_pipeline(mock_config)

        # Assert
        assert mock_pipeline.call_count == 2
        # Vérifier que insert et update ont été appelés
        calls = mock_pipeline.call_args_list
        assert calls[0][1]['process_type'] == 'insert'
        assert calls[1][1]['process_type'] == 'update'

    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.home_station_eligibility_pipeline')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.rp.get_collaborators_to_update')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.rp.get_collaborators_to_process')
    def test_run_pipeline_no_updates(self, mock_get_to_process, mock_get_to_update, mock_pipeline, mock_config):
        """Test pipeline sans updates"""
        # Arrange
        mock_df_insert = pd.DataFrame([{"id": "123", "full_address": "10 RUE PARIS"}])
        mock_df_update = pd.DataFrame(columns=["id", "full_address"])  # DataFrame vide
        
        mock_get_to_process.return_value = mock_df_insert
        mock_get_to_update.return_value = mock_df_update

        # Act
        run_pipeline(mock_config)

        # Assert
        assert mock_pipeline.call_count == 1  # Seulement insert, pas de update
        mock_pipeline.assert_called_once_with(config=mock_config, df=mock_df_insert, process_type='insert')

    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.home_station_eligibility_pipeline')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.rp.get_collaborators_to_update')
    @patch('infrastructure.lambdas.home_station_eligibility.eligibility_pipeline.pipeline.rp.get_collaborators_to_process')
    def test_run_pipeline_empty_data(self, mock_get_to_process, mock_get_to_update, mock_pipeline, mock_config):
        """Test pipeline avec données vides"""
        # Arrange
        empty_df = pd.DataFrame(columns=["id", "full_address"])
        
        mock_get_to_process.return_value = empty_df
        mock_get_to_update.return_value = empty_df

        # Act
        run_pipeline(mock_config)

        # Assert
        assert mock_pipeline.call_count == 1  # Seulement insert appelé