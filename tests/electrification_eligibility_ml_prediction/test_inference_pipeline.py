import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch


# ── config & helpers ──────────────────────────────────────────────────────────

CONFIG = {
    "scores_table": "electrification_scores",
    "scores_m_view": "electrification_scores_today",
    "schema": "publ",
    "model_folder": "models",
    "bucket_name": "test-bucket",
}

def make_features_df(n=20):
    np.random.seed(42)
    return pd.DataFrame({
        "vehicle_id":  [f"V{i:03d}" for i in range(n)],
        "age":         np.random.uniform(0, 10, n),
        "mileage":     np.random.uniform(0, 500, n),
        "energy_type": np.random.choice(["DIESEL", "PETROL"], n),
    })


@pytest.fixture
def pipeline():
    """InferencePipeline avec DataLoader et ElectrificationModel mockés."""
    with patch("soongo_data.utils.eligibility_electrif_predict.inference_pipeline.DataLoader") as MockDL, \
         patch("soongo_data.utils.eligibility_electrif_predict.inference_pipeline.ElectrificationModel") as MockEM, \
         patch("soongo_data.utils.logging_utils.gen_logger", return_value=MagicMock()):

        mock_loader = MagicMock()
        mock_loader.load_data.return_value = make_features_df()
        MockDL.return_value = mock_loader

        mock_model = MagicMock()
        mock_model.predict_score.return_value = np.random.uniform(0, 100, 20)
        mock_model.model_type = "random_forest"
        MockEM.return_value = mock_model

        from soongo_data.utils.eligibility_electrif_predict.inference_pipeline import InferencePipeline
        p = InferencePipeline(config=CONFIG)

    return p


# ── __init__ ──────────────────────────────────────────────────────────────────

def test_init_config_stored(pipeline):
    assert pipeline.config == CONFIG

def test_init_predictions_none(pipeline):
    assert pipeline.predictions is None

def test_init_data_loader_created(pipeline):
    assert pipeline.data_loader is not None

def test_init_model_created(pipeline):
    assert pipeline.model is not None


# ── run ───────────────────────────────────────────────────────────────────────

def test_run_calls_load_data(pipeline):
    pipeline.run()
    pipeline.data_loader.load_data.assert_called_once()

def test_run_calls_predict_score(pipeline):
    pipeline.run()
    pipeline.model.predict_score.assert_called_once()

def test_run_calls_write_results_to_db(pipeline):
    pipeline.run()
    pipeline.data_loader.write_results_to_db.assert_called_once()

def test_run_calls_remove_model_folder(pipeline):
    pipeline.run()
    pipeline.model.remove_model_folder_from_local.assert_called_once()

def test_run_returns_dataframe(pipeline):
    result = pipeline.run()
    assert isinstance(result, pd.DataFrame)

def test_run_adds_score_column(pipeline):
    result = pipeline.run()
    assert "score" in result.columns

def test_run_vehicle_id_in_result(pipeline):
    result = pipeline.run()
    assert "vehicle_id" in result.columns

def test_run_write_db_receives_vehicle_id_and_score(pipeline):
    pipeline.run()
    df_written = pipeline.data_loader.write_results_to_db.call_args[0][0]
    assert "vehicle_id" in df_written.columns
    assert "score" in df_written.columns

def test_run_write_db_receives_model_column(pipeline):
    pipeline.run()
    df_written = pipeline.data_loader.write_results_to_db.call_args[0][0]
    assert "model" in df_written.columns

def test_run_model_column_value(pipeline):
    pipeline.run()
    df_written = pipeline.data_loader.write_results_to_db.call_args[0][0]
    assert df_written["model"].iloc[0] == "random_forest"

def test_run_raises_on_load_data_failure(pipeline):
    pipeline.data_loader.load_data.side_effect = RuntimeError("DB down")
    with pytest.raises(RuntimeError, match="DB down"):
        pipeline.run()

def test_run_raises_on_predict_failure(pipeline):
    pipeline.model.predict_score.side_effect = ValueError("Predict failed")
    with pytest.raises(ValueError, match="Predict failed"):
        pipeline.run()

def test_run_raises_on_write_failure(pipeline):
    pipeline.data_loader.write_results_to_db.side_effect = Exception("Write failed")
    with pytest.raises(Exception, match="Write failed"):
        pipeline.run()

def test_run_predict_score_called_without_vehicle_id(pipeline):
    pipeline.run()
    df_passed = pipeline.model.predict_score.call_args[0][0]
    assert "vehicle_id" not in df_passed.columns


# ── run_pipeline ──────────────────────────────────────────────────────────────

def test_run_pipeline_creates_and_runs(tmp_path):
    with patch("soongo_data.utils.eligibility_electrif_predict.inference_pipeline.InferencePipeline") as MockP:
        mock_instance = MagicMock()
        MockP.return_value = mock_instance
        from soongo_data.utils.eligibility_electrif_predict.inference_pipeline import run_pipeline
        run_pipeline(config=CONFIG)
    MockP.assert_called_once_with(config=CONFIG)
    mock_instance.run.assert_called_once()

def test_run_pipeline_propagates_exception():
    with patch("soongo_data.utils.eligibility_electrif_predict.inference_pipeline.InferencePipeline") as MockP:
        mock_instance = MagicMock()
        mock_instance.run.side_effect = RuntimeError("Pipeline broke")
        MockP.return_value = mock_instance
        from soongo_data.utils.eligibility_electrif_predict.inference_pipeline import run_pipeline
        with pytest.raises(RuntimeError, match="Pipeline broke"):
            run_pipeline(config=CONFIG)