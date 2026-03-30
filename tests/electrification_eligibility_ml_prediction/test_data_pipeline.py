import os
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch


# ── config ───
CONFIG = {
    "scores_table": "electrification_scores",
    "scores_m_view": "electrification_scores_today",
    "schema": "publ",
}


# ── helper ───

def make_df(n=10):
    return pd.DataFrame({
        "vehicle_id": [f"V{i:03d}" for i in range(n)],
        "score":      np.random.uniform(0, 100, n),
        "model":      ["random_forest"] * n,
    })


@pytest.fixture
def loader():
    with patch("soongo_data.utils.db.gen_engine", return_value=MagicMock()), \
         patch("soongo_data.utils.logging_utils.gen_logger", return_value=MagicMock()), \
         patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
        from soongo_data.utils.eligibility_electrif_predict.data_pipeline import DataLoader
        return DataLoader(config=CONFIG)


# ── __init__ ───

def test_init_engine_created(loader):
    assert loader.engine is not None

def test_init_config_stored(loader):
    assert loader.config == CONFIG

def test_init_no_output_table_attr(loader):
    assert not hasattr(loader, "output_table")
    assert not hasattr(loader, "output_mv")
    assert not hasattr(loader, "schema")


# ── load_data ───

def test_load_data_returns_dataframe(loader):
    sample = make_df()
    mock_conn = MagicMock()
    loader.engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    loader.engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with patch("soongo_data.utils.eligibility_electrif_predict.data_pipeline.pd.read_sql", return_value=sample):
        result = loader.load_data()

    assert isinstance(result, pd.DataFrame)

def test_load_data_returns_correct_rows(loader):
    sample = make_df(15)
    mock_conn = MagicMock()
    loader.engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    loader.engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with patch("soongo_data.utils.eligibility_electrif_predict.data_pipeline.pd.read_sql", return_value=sample):
        result = loader.load_data()

    assert len(result) == 15

def test_load_data_raises_on_error(loader):
    mock_conn = MagicMock()
    loader.engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    loader.engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with patch("soongo_data.utils.eligibility_electrif_predict.data_pipeline.pd.read_sql",
               side_effect=Exception("DB error")):
        with pytest.raises(Exception, match="DB error"):
            loader.load_data()

def test_load_data_uses_text_query(loader):
    """Vérifie que load_data passe bien un objet text() à pd.read_sql"""
    sample = make_df()
    mock_conn = MagicMock()
    loader.engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    loader.engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with patch("soongo_data.utils.eligibility_electrif_predict.data_pipeline.pd.read_sql",
               return_value=sample) as mock_read_sql:
        loader.load_data()

    call_args = mock_read_sql.call_args
    from sqlalchemy import TextClause
    assert isinstance(call_args[0][0], TextClause)


# ── delete_todays_rows ───

def test_delete_todays_rows_executes_sql(loader):
    mock_conn = MagicMock()
    loader.delete_todays_rows(mock_conn)
    mock_conn.execute.assert_called_once()

def test_delete_todays_rows_targets_correct_table(loader):
    mock_conn = MagicMock()
    loader.delete_todays_rows(mock_conn)
    sql_arg = mock_conn.execute.call_args[0][0]
    assert "vehicles_electrification_eligibility_score" in str(sql_arg)

def test_delete_todays_rows_filters_on_current_date(loader):
    mock_conn = MagicMock()
    loader.delete_todays_rows(mock_conn)
    sql_arg = mock_conn.execute.call_args[0][0]
    assert "CURRENT_DATE" in str(sql_arg)


# ── insert_predictions_to_table ───

def test_insert_predictions_calls_bulk_insert(loader):
    df = make_df()
    mock_session = MagicMock()

    with patch("soongo_data.utils.eligibility_electrif_predict.data_pipeline.Table"), \
         patch("soongo_data.utils.eligibility_electrif_predict.data_pipeline.MetaData"), \
         patch("soongo_data.utils.eligibility_electrif_predict.data_pipeline.registry"), \
         patch("soongo_data.utils.eligibility_electrif_predict.data_pipeline.Session") as mock_session_cls:

        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        loader.insert_predictions_to_table(df)

    mock_session.bulk_insert_mappings.assert_called_once()
    mock_session.commit.assert_called_once()

def test_insert_predictions_passes_correct_records(loader):
    df = make_df(5)
    mock_session = MagicMock()

    with patch("soongo_data.utils.eligibility_electrif_predict.data_pipeline.Table"), \
         patch("soongo_data.utils.eligibility_electrif_predict.data_pipeline.MetaData"), \
         patch("soongo_data.utils.eligibility_electrif_predict.data_pipeline.registry"), \
         patch("soongo_data.utils.eligibility_electrif_predict.data_pipeline.Session") as mock_session_cls:

        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        loader.insert_predictions_to_table(df)

    records_passed = mock_session.bulk_insert_mappings.call_args[0][1]
    assert len(records_passed) == 5


# ── write_results_to_db ───

def test_write_results_calls_delete_and_insert(loader):
    df = make_df()
    mock_conn = MagicMock()
    loader.engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    loader.engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    with patch.object(loader, "delete_todays_rows") as mock_delete, \
         patch.object(loader, "insert_predictions_to_table") as mock_insert:
        loader.write_results_to_db(df)

    mock_delete.assert_called_once_with(mock_conn)
    mock_insert.assert_called_once_with(df)

def test_write_results_no_longer_calls_ensure_or_refresh(loader):
    df = make_df()
    mock_conn = MagicMock()
    loader.engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    loader.engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    with patch.object(loader, "delete_todays_rows"), \
         patch.object(loader, "insert_predictions_to_table"):
        loader.write_results_to_db(df)

    assert not hasattr(loader, "ensure_table_exist")
    assert not hasattr(loader, "refresh_today_materialized_view")

def test_write_results_raises_on_error(loader):
    df = make_df()
    mock_conn = MagicMock()
    loader.engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    loader.engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    with patch.object(loader, "delete_todays_rows", side_effect=Exception("DB failed")):
        with pytest.raises(Exception, match="DB failed"):
            loader.write_results_to_db(df)

def test_write_results_uses_transaction(loader):
    """write_results_to_db doit utiliser engine.begin() (transaction atomique)"""
    df = make_df()
    mock_conn = MagicMock()
    loader.engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    loader.engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    loader.engine.begin.reset_mock()

    with patch.object(loader, "delete_todays_rows"), \
         patch.object(loader, "insert_predictions_to_table"):
        loader.write_results_to_db(df)

    loader.engine.begin.assert_called_once()