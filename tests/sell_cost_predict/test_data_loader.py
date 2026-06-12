"""
Tests unitaires pour data_loader.py - Sell Cost Predict
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from soongo_data.utils.sell_cost_predict.data_loader import DataLoader


@pytest.fixture
def mock_config():
    """Configuration de test"""
    return {
        "bucket_name": "test-bucket",
        "model_folder": "models"
    }


@pytest.fixture
def sample_data():
    """Données de test alignées avec les features sell cost"""
    return pd.DataFrame({
        'vehicle_id':   ['v1', 'v2', 'v3'],
        'brand':        ['Toyota', 'Ford', 'Honda'],
        'entry_year':   [2020, 2019, 2021],
        'age':          [6, 7, 5],
        'segment':      ['SUV', 'Berline', 'SUV'],
        'energy':       ['Diesel', 'Petrol', 'Electric'],
        'fiscal_power': [6.0, 7.0, 5.0],
        'seat_count':   [5.0, 5.0, 5.0],
        'transmission': ['Manual', 'Auto', 'Auto'],
        'motor_power':  [110.0, 130.0, 150.0],
    })


class TestDataLoader:
    """Tests pour DataLoader"""

    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_init(self, mock_gen_engine, mock_config):
        """Test initialisation du DataLoader"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine

        loader = DataLoader(mock_config)

        assert loader.config == mock_config
        assert loader.engine == mock_engine

    @patch('soongo_data.utils.sell_cost_predict.data_loader.pd.read_sql')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_load_data_success(self, mock_gen_engine, mock_read_sql, mock_config, sample_data):
        """Test chargement des données avec succès"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine
        mock_read_sql.return_value = sample_data

        loader = DataLoader(mock_config)
        result = loader.load_data()

        assert len(result) == 3
        assert 'vehicle_id' in result.columns
        mock_read_sql.assert_called_once()

    @patch('soongo_data.utils.sell_cost_predict.data_loader.pd.read_sql')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_load_data_failure(self, mock_gen_engine, mock_read_sql, mock_config):
        """Test échec du chargement des données"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine
        mock_read_sql.side_effect = Exception("Database error")

        loader = DataLoader(mock_config)

        with pytest.raises(Exception):
            loader.load_data()

    @patch('soongo_data.utils.sell_cost_predict.data_loader.registry')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.Session')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.Table')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_insert_predictions_to_table(self, mock_gen_engine, mock_table, mock_session, mock_registry, mock_config, sample_data):
        """Test insertion des prédictions dans la table"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine
        mock_session_instance = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_instance

        mock_registry_instance = MagicMock()
        mock_registry.return_value = mock_registry_instance

        loader = DataLoader(mock_config)
        loader.insert_predictions_to_table(sample_data)

        mock_session_instance.bulk_insert_mappings.assert_called_once()
        mock_session_instance.commit.assert_called_once()

    @patch('soongo_data.utils.sell_cost_predict.data_loader.registry')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.Session')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.Table')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_insert_predictions_failure(self, mock_gen_engine, mock_table, mock_session, mock_registry, mock_config, sample_data):
        """Test échec de l'insertion"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine
        mock_session_instance = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_instance
        mock_session_instance.bulk_insert_mappings.side_effect = Exception("Insert error")

        mock_registry_instance = MagicMock()
        mock_registry.return_value = mock_registry_instance

        loader = DataLoader(mock_config)

        with pytest.raises(Exception):
            loader.insert_predictions_to_table(sample_data)

    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_delete_todays_rows(self, mock_gen_engine, mock_config):
        """Test suppression des lignes du jour"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine
        mock_conn = MagicMock()

        loader = DataLoader(mock_config)
        loader.delete_todays_rows(mock_conn)

        mock_conn.execute.assert_called_once()

    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_delete_todays_rows_failure(self, mock_gen_engine, mock_config):
        """Test échec de la suppression"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("Delete error")

        loader = DataLoader(mock_config)

        with pytest.raises(Exception):
            loader.delete_todays_rows(mock_conn)

    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_write_results_to_db(self, mock_gen_engine, mock_config, sample_data):
        """Test écriture des résultats en DB"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn

        loader = DataLoader(mock_config)
        loader.delete_todays_rows = MagicMock()
        loader.insert_predictions_to_table = MagicMock()

        loader.write_results_to_db(sample_data)

        loader.delete_todays_rows.assert_called_once_with(mock_conn)
        loader.insert_predictions_to_table.assert_called_once_with(sample_data)

    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_write_results_to_db_failure(self, mock_gen_engine, mock_config, sample_data):
        """Test échec de l'écriture en DB"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine
        mock_engine.begin.return_value.__enter__.side_effect = Exception("Write error")

        loader = DataLoader(mock_config)

        with pytest.raises(Exception):
            loader.write_results_to_db(sample_data)

    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_insert_targets_correct_table(self, mock_gen_engine, mock_config, sample_data):
        """Test que l'insertion cible bien la table vehicles_sell_cost_predictions"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine

        loader = DataLoader(mock_config)

        with patch('soongo_data.utils.sell_cost_predict.data_loader.Table') as mock_table, \
             patch('soongo_data.utils.sell_cost_predict.data_loader.Session') as mock_session, \
             patch('soongo_data.utils.sell_cost_predict.data_loader.registry'):

            mock_session.return_value.__enter__.return_value = MagicMock()
            loader.insert_predictions_to_table(sample_data)

            call_args = mock_table.call_args
            assert call_args[0][0] == "vehicles_sell_cost_predictions"