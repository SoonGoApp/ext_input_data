"""
Tests unitaires pour data_loader.py
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from soongo_data.utils.rent_cost_predict.data_loader import DataLoader


@pytest.fixture
def mock_config():
    """Configuration de test"""
    return {
        "bucket_name": "test-bucket",
        "model_folder": "models"
    }


@pytest.fixture
def sample_data():
    """Données de test"""
    return pd.DataFrame({
        'vehicle_id': ['v1', 'v2', 'v3'],
        'brand': ['Toyota', 'Ford', 'Honda'],
        'year': [2020, 2019, 2021],
        'predicted_rent_cost': [500, 600, 550]
    })


def make_mock_engine(sample_data, execute_side_effect=None):
    """Construit un mock d'engine SQLAlchemy tel qu'utilisé par
    load_data(): `with engine.connect() as conn: conn.execute(text(...))`
    puis `pd.DataFrame(result.fetchall(), columns=result.keys())`.
    """
    mock_engine = MagicMock()
    mock_conn = MagicMock()

    if execute_side_effect is not None:
        mock_conn.execute.side_effect = execute_side_effect
    else:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = list(
            sample_data.itertuples(index=False, name=None)
        )
        mock_result.keys.return_value = list(sample_data.columns)
        mock_conn.execute.return_value = mock_result

    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_engine.connect.return_value.__exit__.return_value = False
    return mock_engine, mock_conn


class TestDataLoader:
    """Tests pour DataLoader"""

    @patch('soongo_data.utils.rent_cost_predict.data_loader.gen_engine')
    def test_init(self, mock_gen_engine, mock_config):
        """Test initialisation du DataLoader"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine

        loader = DataLoader(mock_config)

        assert loader.config == mock_config
        assert loader.engine == mock_engine

    @patch('soongo_data.utils.rent_cost_predict.data_loader.gen_engine')
    def test_load_data_success(self, mock_gen_engine, mock_config, sample_data):
        """Test chargement des données avec succès"""
        mock_engine, mock_conn = make_mock_engine(sample_data)
        mock_gen_engine.return_value = mock_engine

        loader = DataLoader(mock_config)
        result = loader.load_data()

        assert len(result) == 3
        assert 'vehicle_id' in result.columns
        mock_conn.execute.assert_called_once()

    @patch('soongo_data.utils.rent_cost_predict.data_loader.gen_engine')
    def test_load_data_uses_text_clause(self, mock_gen_engine, mock_config, sample_data):
        """Test que la requête passe bien par text(...) et pas par pd.read_sql
        (source du bug 'Query must be a string unless using sqlalchemy')."""
        mock_engine, mock_conn = make_mock_engine(sample_data)
        mock_gen_engine.return_value = mock_engine

        loader = DataLoader(mock_config)
        loader.load_data()

        executed_query = mock_conn.execute.call_args[0][0]
        assert hasattr(executed_query, "text") or "TextClause" in type(executed_query).__name__

    @patch('soongo_data.utils.rent_cost_predict.data_loader.gen_engine')
    def test_load_data_failure(self, mock_gen_engine, mock_config):
        """Test échec du chargement des données"""
        mock_engine, mock_conn = make_mock_engine(
            sample_data=None,
            execute_side_effect=Exception("Database error"),
        )
        mock_gen_engine.return_value = mock_engine

        loader = DataLoader(mock_config)

        with pytest.raises(Exception):
            loader.load_data()

    @patch('soongo_data.utils.rent_cost_predict.data_loader.registry')
    @patch('soongo_data.utils.rent_cost_predict.data_loader.Session')
    @patch('soongo_data.utils.rent_cost_predict.data_loader.Table')
    @patch('soongo_data.utils.rent_cost_predict.data_loader.gen_engine')
    def test_insert_predictions_to_table(self, mock_gen_engine, mock_table, mock_session, mock_registry, mock_config, sample_data):
        """Test insertion des prédictions dans la table"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine
        mock_session_instance = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_instance

        # Mock du registry pour éviter l'exécution réelle de map_imperatively
        mock_registry_instance = MagicMock()
        mock_registry.return_value = mock_registry_instance

        loader = DataLoader(mock_config)
        loader.insert_predictions_to_table(sample_data)

        mock_session_instance.bulk_insert_mappings.assert_called_once()
        mock_session_instance.commit.assert_called_once()

    @patch('soongo_data.utils.rent_cost_predict.data_loader.registry')
    @patch('soongo_data.utils.rent_cost_predict.data_loader.Session')
    @patch('soongo_data.utils.rent_cost_predict.data_loader.Table')
    @patch('soongo_data.utils.rent_cost_predict.data_loader.gen_engine')
    def test_insert_predictions_failure(self, mock_gen_engine, mock_table, mock_session, mock_registry, mock_config, sample_data):
        """Test échec de l'insertion"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine
        mock_session_instance = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_instance
        mock_session_instance.bulk_insert_mappings.side_effect = Exception("Insert error")

        # Mock du registry
        mock_registry_instance = MagicMock()
        mock_registry.return_value = mock_registry_instance

        loader = DataLoader(mock_config)

        with pytest.raises(Exception):
            loader.insert_predictions_to_table(sample_data)

    @patch('soongo_data.utils.rent_cost_predict.data_loader.gen_engine')
    def test_delete_todays_rows(self, mock_gen_engine, mock_config):
        """Test suppression des lignes du jour"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine
        mock_conn = MagicMock()

        loader = DataLoader(mock_config)
        loader.delete_todays_rows(mock_conn)

        mock_conn.execute.assert_called_once()

    @patch('soongo_data.utils.rent_cost_predict.data_loader.gen_engine')
    def test_delete_todays_rows_failure(self, mock_gen_engine, mock_config):
        """Test échec de la suppression"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("Delete error")

        loader = DataLoader(mock_config)

        with pytest.raises(Exception):
            loader.delete_todays_rows(mock_conn)

    @patch('soongo_data.utils.rent_cost_predict.data_loader.gen_engine')
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

    @patch('soongo_data.utils.rent_cost_predict.data_loader.gen_engine')
    def test_write_results_to_db_failure(self, mock_gen_engine, mock_config, sample_data):
        """Test échec de l'écriture en DB"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine
        mock_engine.begin.return_value.__enter__.side_effect = Exception("Write error")

        loader = DataLoader(mock_config)

        with pytest.raises(Exception):
            loader.write_results_to_db(sample_data)