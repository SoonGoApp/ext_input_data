"""
Tests unitaires pour data_loader.py - Sell Cost Predict
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from soongo_data.utils.sell_cost_predict.data_loader import DataLoader


@pytest.fixture
def mock_config():
    return {
        "bucket_name": "test-bucket",
        "model_folder": "models"
    }


@pytest.fixture
def sample_data():
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


def make_mock_engine(sample_data, execute_side_effect=None):
    """Mock d'engine SQLAlchemy tel qu'utilisé par load_data():
    `with engine.connect() as conn: conn.execute(text(...))` puis
    `pd.DataFrame(result.fetchall(), columns=result.keys())`."""
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

    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_init(self, mock_gen_engine, mock_config):
        """Test initialisation du DataLoader"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine

        loader = DataLoader(mock_config)

        assert loader.config == mock_config
        assert loader.engine == mock_engine

    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_load_data_success(self, mock_gen_engine, mock_config, sample_data):
        """Test chargement des données avec succès"""
        mock_engine, mock_conn = make_mock_engine(sample_data)
        mock_gen_engine.return_value = mock_engine

        loader = DataLoader(mock_config)
        result = loader.load_data()

        assert len(result) == 3
        assert 'vehicle_id' in result.columns
        mock_conn.execute.assert_called_once()

    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_load_data_uses_text_clause(self, mock_gen_engine, mock_config, sample_data):
        """Test que la requête passe par text(...) et pas par pd.read_sql"""
        mock_engine, mock_conn = make_mock_engine(sample_data)
        mock_gen_engine.return_value = mock_engine

        loader = DataLoader(mock_config)
        loader.load_data()

        executed_query = mock_conn.execute.call_args[0][0]
        assert hasattr(executed_query, "text") or "TextClause" in type(executed_query).__name__

    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
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

    @patch('soongo_data.utils.sell_cost_predict.data_loader.MetaData')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.Table')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_insert_predictions_to_table(self, mock_gen_engine, mock_table, mock_metadata, mock_config, sample_data):
        """Insertion SQLAlchemy Core dans la connexion reçue (même transaction que le DELETE)"""
        mock_gen_engine.return_value = MagicMock()
        mock_conn = MagicMock()

        loader = DataLoader(mock_config)
        loader.insert_predictions_to_table(sample_data, mock_conn)

        mock_conn.execute.assert_called_once()
        records = mock_conn.execute.call_args[0][1]
        assert len(records) == len(sample_data)
        assert records[0]['vehicle_id'] == 'v1'

    @patch('soongo_data.utils.sell_cost_predict.data_loader.MetaData')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.Table')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_insert_predictions_batches_by_1000(self, mock_gen_engine, mock_table, mock_metadata, mock_config):
        mock_gen_engine.return_value = MagicMock()
        mock_conn = MagicMock()
        df = pd.DataFrame({'vehicle_id': [f"v{i}" for i in range(2500)], 'predicted_value': 1.0})

        DataLoader(mock_config).insert_predictions_to_table(df, mock_conn)

        assert mock_conn.execute.call_count == 3                          # 1000 + 1000 + 500
        sizes = [len(c[0][1]) for c in mock_conn.execute.call_args_list]
        assert sizes == [1000, 1000, 500]

    @patch('soongo_data.utils.sell_cost_predict.data_loader.MetaData')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.Table')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_insert_predictions_failure(self, mock_gen_engine, mock_table, mock_metadata, mock_config, sample_data):
        """Échec de l'insertion : l'exception remonte (la transaction est annulée par l'appelant)"""
        mock_gen_engine.return_value = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("Insert error")

        with pytest.raises(Exception, match="Insert error"):
            DataLoader(mock_config).insert_predictions_to_table(sample_data, mock_conn)

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
        loader.insert_predictions_to_table.assert_called_once_with(sample_data, mock_conn)

    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_write_results_to_db_failure(self, mock_gen_engine, mock_config, sample_data):
        """Test échec de l'écriture en DB"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine
        mock_engine.begin.return_value.__enter__.side_effect = Exception("Write error")

        loader = DataLoader(mock_config)

        with pytest.raises(Exception):
            loader.write_results_to_db(sample_data)

    @patch('soongo_data.utils.sell_cost_predict.data_loader.MetaData')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.Table')
    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_insert_targets_correct_table(self, mock_gen_engine, mock_table, mock_metadata, mock_config, sample_data):
        """L'insertion cible bien publ.vehicles_sell_cost_predictions"""
        mock_gen_engine.return_value = MagicMock()

        DataLoader(mock_config).insert_predictions_to_table(sample_data, MagicMock())

        assert mock_table.call_args[0][0] == "vehicles_sell_cost_predictions"
        assert mock_metadata.call_args[1] == {"schema": "publ"}

    @patch('soongo_data.utils.sell_cost_predict.data_loader.gen_engine')
    def test_write_results_deletes_then_inserts_in_same_transaction(self, mock_gen_engine, mock_config, sample_data):
        """DELETE et INSERT utilisent la même connexion, ouverte avec engine.begin() (tout ou rien)"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn
        order = []

        loader = DataLoader(mock_config)
        loader.delete_todays_rows = MagicMock(side_effect=lambda c: order.append(('delete', c)))
        loader.insert_predictions_to_table = MagicMock(side_effect=lambda df, c: order.append(('insert', c)))

        loader.write_results_to_db(sample_data)

        assert order == [('delete', mock_conn), ('insert', mock_conn)]
        mock_engine.begin.assert_called_once()