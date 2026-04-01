import os
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch


# ── helpers ───

def make_df(n=10):
    return pd.DataFrame({
        "age":         [i * 1.0 for i in range(n)],
        "mileage":     [i * 100.0 for i in range(n)],
        "energy_type": ["DIESEL"] * n,
        "target":      [0, 1] * (n // 2),
    })


@pytest.fixture
def loader():
    with patch("soongo_data.utils.eligibility_electrif_training.data_pipeline.gen_engine", return_value=MagicMock()), \
         patch("soongo_data.utils.eligibility_electrif_training.data_pipeline.logger", MagicMock()), \
         patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}):
        from soongo_data.utils.eligibility_electrif_training.data_pipeline import DataLoader
        return DataLoader()


# ── __init__ ───

def test_loader_has_engine(loader):
    assert loader.engine is not None


# ── load_data ───

def test_load_data_returns_dataframe(loader):
    sample = make_df()
    with patch("soongo_data.utils.eligibility_electrif_training.data_pipeline.pd.read_sql", return_value=sample):
        result = loader.load_data()
    assert isinstance(result, pd.DataFrame)

def test_load_data_returns_correct_rows(loader):
    sample = make_df(n=10)
    with patch("soongo_data.utils.eligibility_electrif_training.data_pipeline.pd.read_sql", return_value=sample):
        result = loader.load_data()
    assert len(result) == 10

def test_load_data_has_target_column(loader):
    sample = make_df()
    with patch("soongo_data.utils.eligibility_electrif_training.data_pipeline.pd.read_sql", return_value=sample):
        result = loader.load_data()
    assert "target" in result.columns

def test_load_data_raises_on_error(loader):
    with patch(
        "soongo_data.utils.eligibility_electrif_training.data_pipeline.pd.read_sql",
        side_effect=Exception("DB error")
    ):
        with pytest.raises(Exception, match="DB error"):
            loader.load_data()