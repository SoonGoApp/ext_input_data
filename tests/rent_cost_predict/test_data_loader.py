# ===================== test_data_loader.py =====================
"""
Tests unitaires pour data_loader.py (rent)
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from soongo_data.utils.rent_cost_predict.data_loader import DataLoader

MODULE = 'soongo_data.utils.rent_cost_predict.data_loader'


@pytest.fixture
def mock_config():
    return {"bucket_name": "test-bucket", "model_folder": "models"}


@pytest.fixture
def sample_data():
    return pd.DataFrame({
        'vehicle_id': ['v1', 'v2', 'v3'],
        'brand': ['Toyota', 'Ford', 'Honda'],
        'year': [2020, 2019, 2021],
        'predicted_rent_cost': [500, 600, 550],
    })


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")


def make_mock_engine(sample_data, execute_side_effect=None):
    engine = MagicMock()
    conn = MagicMock()
    if execute_side_effect is not None:
        conn.execute.side_effect = execute_side_effect
    else:
        result = MagicMock()
        result.fetchall.return_value = list(sample_data.itertuples(index=False, name=None))
        result.keys.return_value = list(sample_data.columns)
        conn.execute.return_value = result
    engine.connect.return_value.__enter__.return_value = conn
    engine.connect.return_value.__exit__.return_value = False
    return engine, conn


@patch(f'{MODULE}.gen_engine')
class TestInit:

    def test_init(self, mock_gen_engine, mock_config, env):
        engine = MagicMock()
        mock_gen_engine.return_value = engine

        loader = DataLoader(mock_config)

        assert loader.config == mock_config
        assert loader.engine is engine

    def test_init_uses_database_url_env(self, mock_gen_engine, mock_config, env):
        DataLoader(mock_config)
        mock_gen_engine.assert_called_once_with(database_url="postgresql://user:pw@host/db")

    def test_init_without_database_url_raises(self, mock_gen_engine, mock_config, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(KeyError):
            DataLoader(mock_config)


@patch(f'{MODULE}.add_ecb_features', side_effect=lambda df: df)
@patch(f'{MODULE}.gen_engine')
class TestLoadData:

    def test_load_data_success(self, mock_gen_engine, mock_ecb, mock_config, sample_data, env):
        engine, conn = make_mock_engine(sample_data)
        mock_gen_engine.return_value = engine

        result = DataLoader(mock_config).load_data()

        assert len(result) == 3
        assert list(result.columns) == list(sample_data.columns)
        conn.execute.assert_called_once()

    def test_uses_text_clause_with_prediction_query(self, mock_gen_engine, mock_ecb, mock_config, sample_data, env):
        from soongo_data.utils.rent_cost_predict.sql_requests import SELECT_ALL_FEATURES_PREDICTION
        engine, conn = make_mock_engine(sample_data)
        mock_gen_engine.return_value = engine

        DataLoader(mock_config).load_data()

        query = conn.execute.call_args[0][0]
        assert "TextClause" in type(query).__name__
        assert str(query) == SELECT_ALL_FEATURES_PREDICTION

    def test_ecb_features_added(self, mock_gen_engine, mock_ecb, mock_config, sample_data, env):
        mock_ecb.side_effect = lambda df: df.assign(ecb_rate=2.0, interest_per_month=5.0)
        engine, _ = make_mock_engine(sample_data)
        mock_gen_engine.return_value = engine

        result = DataLoader(mock_config).load_data()

        mock_ecb.assert_called_once()
        assert {'ecb_rate', 'interest_per_month'} <= set(result.columns)

    def test_ecb_skipped_when_empty(self, mock_gen_engine, mock_ecb, mock_config, sample_data, env):
        engine, _ = make_mock_engine(sample_data.iloc[0:0])
        mock_gen_engine.return_value = engine

        result = DataLoader(mock_config).load_data()

        assert result.empty
        mock_ecb.assert_not_called()

    def test_sql_failure_raises(self, mock_gen_engine, mock_ecb, mock_config, env):
        engine, _ = make_mock_engine(None, execute_side_effect=Exception("Database error"))
        mock_gen_engine.return_value = engine

        with pytest.raises(Exception, match="Database error"):
            DataLoader(mock_config).load_data()

    def test_ecb_failure_raises(self, mock_gen_engine, mock_ecb, mock_config, sample_data, env):
        mock_ecb.side_effect = RuntimeError("ECB down")
        engine, _ = make_mock_engine(sample_data)
        mock_gen_engine.return_value = engine

        with pytest.raises(RuntimeError, match="ECB down"):
            DataLoader(mock_config).load_data()


@patch(f'{MODULE}.registry')
@patch(f'{MODULE}.Session')
@patch(f'{MODULE}.Table')
@patch(f'{MODULE}.gen_engine')
class TestInsertPredictions:

    def _setup(self, mock_gen_engine, mock_session):
        engine = MagicMock()
        mock_gen_engine.return_value = engine
        session = MagicMock()
        mock_session.return_value.__enter__.return_value = session
        return engine, session

    def test_insert_success(self, mock_gen_engine, mock_table, mock_session, mock_registry,
                            mock_config, sample_data, env):
        _, session = self._setup(mock_gen_engine, mock_session)

        DataLoader(mock_config).insert_predictions_to_table(sample_data)

        session.bulk_insert_mappings.assert_called_once()
        session.commit.assert_called_once()

    def test_reflects_correct_table(self, mock_gen_engine, mock_table, mock_session, mock_registry,
                                    mock_config, sample_data, env):
        engine, _ = self._setup(mock_gen_engine, mock_session)

        DataLoader(mock_config).insert_predictions_to_table(sample_data)

        args, kwargs = mock_table.call_args
        assert args[0] == "vehicles_rent_cost_predictions"
        assert args[1].schema == "publ"
        assert kwargs['autoload_with'] is engine

    def test_records_passed_as_dicts(self, mock_gen_engine, mock_table, mock_session, mock_registry,
                                     mock_config, sample_data, env):
        _, session = self._setup(mock_gen_engine, mock_session)

        DataLoader(mock_config).insert_predictions_to_table(sample_data)

        records = session.bulk_insert_mappings.call_args[0][1]
        assert records == sample_data.to_dict(orient="records")

    def test_table_is_mapped_imperatively(self, mock_gen_engine, mock_table, mock_session, mock_registry,
                                          mock_config, sample_data, env):
        self._setup(mock_gen_engine, mock_session)

        DataLoader(mock_config).insert_predictions_to_table(sample_data)

        mock_registry.return_value.map_imperatively.assert_called_once()
        assert mock_registry.return_value.map_imperatively.call_args[0][1] is mock_table.return_value

    def test_insert_failure_raises_and_no_commit(self, mock_gen_engine, mock_table, mock_session, mock_registry,
                                                 mock_config, sample_data, env):
        _, session = self._setup(mock_gen_engine, mock_session)
        session.bulk_insert_mappings.side_effect = Exception("Insert error")

        with pytest.raises(Exception, match="Insert error"):
            DataLoader(mock_config).insert_predictions_to_table(sample_data)

        session.commit.assert_not_called()

    def test_table_reflection_failure_raises(self, mock_gen_engine, mock_table, mock_session, mock_registry,
                                             mock_config, sample_data, env):
        self._setup(mock_gen_engine, mock_session)
        mock_table.side_effect = Exception("no such table")

        with pytest.raises(Exception, match="no such table"):
            DataLoader(mock_config).insert_predictions_to_table(sample_data)


@patch(f'{MODULE}.gen_engine')
class TestDeleteTodaysRows:

    def test_delete_executes_scoped_sql(self, mock_gen_engine, mock_config, env):
        conn = MagicMock()

        DataLoader(mock_config).delete_todays_rows(conn)

        conn.execute.assert_called_once()
        sql = str(conn.execute.call_args[0][0])
        assert "DELETE FROM publ.vehicles_rent_cost_predictions" in sql
        assert "created_at::date = CURRENT_DATE" in sql

    def test_delete_failure_raises(self, mock_gen_engine, mock_config, env):
        conn = MagicMock()
        conn.execute.side_effect = Exception("Delete error")

        with pytest.raises(Exception, match="Delete error"):
            DataLoader(mock_config).delete_todays_rows(conn)


@patch(f'{MODULE}.gen_engine')
class TestWriteResults:

    def test_write_results_single_transaction(self, mock_gen_engine, mock_config, sample_data, env):
        engine = MagicMock()
        mock_gen_engine.return_value = engine
        conn = MagicMock()
        engine.begin.return_value.__enter__.return_value = conn
        loader = DataLoader(mock_config)
        loader.delete_todays_rows = MagicMock()
        loader.insert_predictions_to_table = MagicMock()

        loader.write_results_to_db(sample_data)

        engine.begin.assert_called_once()
        loader.delete_todays_rows.assert_called_once_with(conn)
        loader.insert_predictions_to_table.assert_called_once_with(sample_data)

    def test_delete_before_insert(self, mock_gen_engine, mock_config, sample_data, env):
        engine = MagicMock()
        mock_gen_engine.return_value = engine
        loader = DataLoader(mock_config)
        calls = []
        loader.delete_todays_rows = MagicMock(side_effect=lambda c: calls.append("delete"))
        loader.insert_predictions_to_table = MagicMock(side_effect=lambda d: calls.append("insert"))

        loader.write_results_to_db(sample_data)

        assert calls == ["delete", "insert"]

    def test_delete_failure_skips_insert(self, mock_gen_engine, mock_config, sample_data, env):
        mock_gen_engine.return_value = MagicMock()
        loader = DataLoader(mock_config)
        loader.delete_todays_rows = MagicMock(side_effect=Exception("Delete error"))
        loader.insert_predictions_to_table = MagicMock()

        with pytest.raises(Exception, match="Delete error"):
            loader.write_results_to_db(sample_data)

        loader.insert_predictions_to_table.assert_not_called()

    def test_insert_failure_propagates(self, mock_gen_engine, mock_config, sample_data, env):
        mock_gen_engine.return_value = MagicMock()
        loader = DataLoader(mock_config)
        loader.delete_todays_rows = MagicMock()
        loader.insert_predictions_to_table = MagicMock(side_effect=Exception("Insert error"))

        with pytest.raises(Exception, match="Insert error"):
            loader.write_results_to_db(sample_data)

    def test_transaction_open_failure(self, mock_gen_engine, mock_config, sample_data, env):
        engine = MagicMock()
        mock_gen_engine.return_value = engine
        engine.begin.return_value.__enter__.side_effect = Exception("Write error")

        with pytest.raises(Exception, match="Write error"):
            DataLoader(mock_config).write_results_to_db(sample_data)