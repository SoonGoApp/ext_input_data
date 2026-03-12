import os
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch, call


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

def test_init_output_table(loader):
    assert loader.output_table == CONFIG["scores_table"]

def test_init_output_mv(loader):
    assert loader.output_mv == CONFIG["scores_m_view"]

def test_init_schema(loader):
    assert loader.schema == CONFIG["schema"]


# ── load_data ───

def test_load_data_returns_dataframe(loader):
    sample = make_df()
    with patch("soongo_data.utils.eligibility_electrif_predict.data_pipeline.pd.read_sql", return_value=sample):
        result = loader.load_data()
    assert isinstance(result, pd.DataFrame)

def test_load_data_returns_correct_rows(loader):
    sample = make_df(15)
    with patch("soongo_data.utils.eligibility_electrif_predict.data_pipeline.pd.read_sql", return_value=sample):
        result = loader.load_data()
    assert len(result) == 15

def test_load_data_raises_on_error(loader):
    with patch("soongo_data.utils.eligibility_electrif_predict.data_pipeline.pd.read_sql",
               side_effect=Exception("DB error")):
        with pytest.raises(Exception, match="DB error"):
            loader.load_data()


# ── ensure_table_exist ───

def test_ensure_table_exist_executes_sql(loader):
    mock_conn = MagicMock()
    loader.ensure_table_exist(mock_conn)
    mock_conn.execute.assert_called_once()

def test_ensure_table_exist_uses_correct_table(loader):
    mock_conn = MagicMock()
    loader.ensure_table_exist(mock_conn)
    sql_arg = mock_conn.execute.call_args[0][0]
    assert CONFIG["scores_table"] in str(sql_arg)


# ── delete_todays_rows ───

def test_delete_todays_rows_executes_sql(loader):
    mock_conn = MagicMock()
    loader.delete_todays_rows(mock_conn)
    mock_conn.execute.assert_called_once()

def test_delete_todays_rows_uses_correct_table(loader):
    mock_conn = MagicMock()
    loader.delete_todays_rows(mock_conn)
    sql_arg = mock_conn.execute.call_args[0][0]
    assert CONFIG["scores_table"] in str(sql_arg)


# ── refresh_today_materialized_view ───

def test_refresh_mv_executes_sql(loader):
    mock_conn = MagicMock()
    loader.refresh_today_materialized_view(mock_conn)
    assert mock_conn.execute.call_count == 2  # DROP + CREATE

def test_refresh_mv_uses_correct_view_name(loader):
    mock_conn = MagicMock()
    loader.refresh_today_materialized_view(mock_conn)
    all_sql = " ".join(str(c[0][0]) for c in mock_conn.execute.call_args_list)
    assert CONFIG["scores_m_view"] in all_sql


# ── write_results_to_db ──

def test_write_results_calls_all_steps(loader):
    df = make_df()
    with patch.object(loader, "ensure_table_exist") as mock_ensure, \
         patch.object(loader, "delete_todays_rows") as mock_delete, \
         patch.object(loader, "insert_predictions_to_table") as mock_insert, \
         patch.object(loader, "refresh_today_materialized_view") as mock_refresh:
        loader.write_results_to_db(df)

    mock_ensure.assert_called_once()
    mock_delete.assert_called_once()
    mock_insert.assert_called_once()
    mock_refresh.assert_called_once()

def test_write_results_raises_on_error(loader):
    df = make_df()
    with patch.object(loader, "ensure_table_exist", side_effect=Exception("DB failed")):
        with pytest.raises(Exception, match="DB failed"):
            loader.write_results_to_db(df)