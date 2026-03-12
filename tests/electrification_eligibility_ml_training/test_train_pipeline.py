import os
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch


CONFIG = {
    "model_type": "random_forest",
    "model_params": {"n_estimators": 10, "max_depth": 3, "random_state": 42},
    "test_size": 0.3,
    "random_state": 42,
    "models_dir": "/tmp/test_models",
    "bucket_name": "test-bucket",
}

def make_df(n=100):
    np.random.seed(42)
    return pd.DataFrame({
        "vehicle_id":  [f"V{i:03d}" for i in range(n)],
        "age":         np.random.uniform(0, 10, n),
        "mileage":     np.random.uniform(0, 500, n),
        "energy_type": np.random.choice(["DIESEL", "PETROL"], n),
        "target":      np.random.randint(0, 2, n),
    })


@pytest.fixture
def pipeline(tmp_path):
    """TrainingPipeline avec DataLoader et ElectrificationModel mockés."""
    cfg = {**CONFIG, "models_dir": str(tmp_path / "models")}
    with patch("soongo_data.utils.eligibility_electrif_training.train_pipeline.DataLoader") as MockDL, \
         patch("soongo_data.utils.eligibility_electrif_training.train_pipeline.ElectrificationModel") as MockEM, \
         patch("soongo_data.utils.logging_utils.gen_logger", return_value=MagicMock()):
        from soongo_data.utils.eligibility_electrif_training.train_pipeline import TrainingPipeline
        p = TrainingPipeline(config=cfg)
    return p


# ── __init__ ───

def test_init_config_stored(tmp_path):
    cfg = {**CONFIG, "models_dir": str(tmp_path / "models")}
    with patch("soongo_data.utils.eligibility_electrif_training.train_pipeline.DataLoader"), \
         patch("soongo_data.utils.eligibility_electrif_training.train_pipeline.ElectrificationModel"), \
         patch("soongo_data.utils.logging_utils.gen_logger", return_value=MagicMock()):
        from soongo_data.utils.eligibility_electrif_training.train_pipeline import TrainingPipeline
        p = TrainingPipeline(config=cfg)
    assert p.config == cfg

def test_init_results_empty(tmp_path):
    cfg = {**CONFIG, "models_dir": str(tmp_path / "models")}
    with patch("soongo_data.utils.eligibility_electrif_training.train_pipeline.DataLoader"), \
         patch("soongo_data.utils.eligibility_electrif_training.train_pipeline.ElectrificationModel"), \
         patch("soongo_data.utils.logging_utils.gen_logger", return_value=MagicMock()):
        from soongo_data.utils.eligibility_electrif_training.train_pipeline import TrainingPipeline
        p = TrainingPipeline(config=cfg)
    assert p.results == {}


# ── setup ───

def test_setup_creates_models_dir(tmp_path):
    cfg = {**CONFIG, "models_dir": str(tmp_path / "models")}
    with patch("soongo_data.utils.eligibility_electrif_training.train_pipeline.DataLoader"), \
         patch("soongo_data.utils.eligibility_electrif_training.train_pipeline.ElectrificationModel"), \
         patch("soongo_data.utils.logging_utils.gen_logger", return_value=MagicMock()):
        from soongo_data.utils.eligibility_electrif_training.train_pipeline import TrainingPipeline
        p = TrainingPipeline(config=cfg)
        p.setup()
    assert (tmp_path / "models").exists()

def test_setup_does_not_raise(pipeline):
    pipeline.setup()  # ne doit pas lever d'exception


# ── save_artifacts ───

def test_save_artifacts_calls_model_save(pipeline):
    pipeline.results = {}
    pipeline.model = MagicMock()
    pipeline.save_artifacts()
    pipeline.model.save_model.assert_called_once()

def test_save_artifacts_returns_path(pipeline):
    pipeline.results = {}
    pipeline.model = MagicMock()
    result = pipeline.save_artifacts()
    assert result is not None


# ── run ───

def _make_pipeline_for_run(tmp_path):
    """Pipeline avec load_data et train_model mockés pour tester run()."""
    cfg = {**CONFIG, "models_dir": str(tmp_path / "models")}
    df  = make_df()

    with patch("soongo_data.utils.eligibility_electrif_training.train_pipeline.DataLoader") as MockDL, \
         patch("soongo_data.utils.eligibility_electrif_training.train_pipeline.ElectrificationModel") as MockEM, \
         patch("soongo_data.utils.logging_utils.gen_logger", return_value=MagicMock()):

        mock_loader = MagicMock()
        mock_loader.load_data.return_value = df
        MockDL.return_value = mock_loader

        mock_model = MagicMock()
        mock_model.train_model.return_value = {"train_metrics": {}}
        MockEM.return_value = mock_model

        from soongo_data.utils.eligibility_electrif_training.train_pipeline import TrainingPipeline
        p = TrainingPipeline(config=cfg)

    return p, mock_loader, mock_model


def test_run_calls_load_data(tmp_path):
    p, mock_loader, _ = _make_pipeline_for_run(tmp_path)
    with patch.object(p, "save_artifacts", return_value=tmp_path):
        p.run()
    mock_loader.load_data.assert_called_once()

def test_run_calls_train_model(tmp_path):
    p, _, mock_model = _make_pipeline_for_run(tmp_path)
    with patch.object(p, "save_artifacts", return_value=tmp_path):
        p.run()
    mock_model.train_model.assert_called_once()

def test_run_calls_save_artifacts(tmp_path):
    p, _, _ = _make_pipeline_for_run(tmp_path)
    with patch.object(p, "save_artifacts", return_value=tmp_path) as mock_save:
        p.run()
    mock_save.assert_called_once()

def test_run_target_not_in_features(tmp_path):
    p, _, mock_model = _make_pipeline_for_run(tmp_path)
    captured = {}
    def capture(features, target):
        captured["features"] = features
        return {}
    mock_model.train_model.side_effect = capture
    with patch.object(p, "save_artifacts", return_value=tmp_path):
        p.run()
    assert "target" not in captured["features"].columns

def test_run_target_df_has_vehicle_id_and_target(tmp_path):
    p, _, mock_model = _make_pipeline_for_run(tmp_path)
    captured = {}
    def capture(features, target):
        captured["target"] = target
        return {}
    mock_model.train_model.side_effect = capture
    with patch.object(p, "save_artifacts", return_value=tmp_path):
        p.run()
    assert "vehicle_id" in captured["target"].columns
    assert "target" in captured["target"].columns

def test_run_returns_model_dir(tmp_path):
    p, _, _ = _make_pipeline_for_run(tmp_path)
    with patch.object(p, "save_artifacts", return_value=tmp_path / "model"):
        result = p.run()
    assert result == tmp_path / "model"

def test_run_raises_on_load_data_failure(tmp_path):
    p, mock_loader, _ = _make_pipeline_for_run(tmp_path)
    mock_loader.load_data.side_effect = RuntimeError("DB down")
    with pytest.raises(RuntimeError, match="DB down"):
        p.run()

def test_run_raises_on_train_failure(tmp_path):
    p, _, mock_model = _make_pipeline_for_run(tmp_path)
    mock_model.train_model.side_effect = ValueError("Training failed")
    with pytest.raises(ValueError, match="Training failed"):
        p.run()


# ── run_pipeline ────

def test_run_pipeline_creates_pipeline_and_runs(tmp_path):
    cfg = {**CONFIG, "models_dir": str(tmp_path / "models")}
    with patch("soongo_data.utils.eligibility_electrif_training.train_pipeline.TrainingPipeline") as MockP:
        mock_instance = MagicMock()
        MockP.return_value = mock_instance
        from soongo_data.utils.eligibility_electrif_training.train_pipeline import run_pipeline
        run_pipeline(config=cfg)
    MockP.assert_called_once_with(config=cfg)
    mock_instance.run.assert_called_once()

def test_run_pipeline_propagates_exception(tmp_path):
    cfg = {**CONFIG, "models_dir": str(tmp_path / "models")}
    with patch("soongo_data.utils.eligibility_electrif_training.train_pipeline.TrainingPipeline") as MockP:
        mock_instance = MagicMock()
        mock_instance.run.side_effect = RuntimeError("Pipeline broke")
        MockP.return_value = mock_instance
        from soongo_data.utils.eligibility_electrif_training.train_pipeline import run_pipeline
        with pytest.raises(RuntimeError, match="Pipeline broke"):
            run_pipeline(config=cfg)