import json
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import MagicMock, patch
from sklearn.preprocessing import LabelEncoder, StandardScaler


# ── config & helpers ──────────────────────────────────────────────────────────

CONFIG = {
    "model_type": "random_forest",
    "models_dir": "/tmp/test_models",
    "bucket_name": "test-bucket",
    "model_folder": "models",
}

def make_df(n=20):
    np.random.seed(42)
    return pd.DataFrame({
        "age":         np.random.uniform(0, 10, n),
        "mileage":     np.random.uniform(0, 500, n),
        "energy_type": np.random.choice(["DIESEL", "PETROL"], n),
    })

def make_metadata():
    return {
        "model_type": "random_forest",
        "feature_names": ["age", "mileage", "energy_type"],
        "categorical_features": ["energy_type"],
        "numeric_features": ["age", "mileage"],
        "metrics": {},
        "median_values": {"age": 5.0, "mileage": 250.0},
    }

def make_scaler_data():
    return {
        "scaler_type": "StandardScaler",
        "mean":  [5.0, 250.0, 0.5],
        "var":   [4.0, 10000.0, 0.25],
        "scale": [2.0, 100.0, 0.5],
        "n_features": 3,
        "with_mean": True,
        "with_std": True,
    }

def make_encoders_data():
    return {
        "energy_type": {"classes": ["DIESEL", "MISSING", "PETROL"]}
    }


@pytest.fixture
def model(tmp_path):
    """ElectrificationModel avec S3 et artifacts mockés."""

    # Le code construit : models_dir / last_model_name
    model_subdir = tmp_path / "model_2024-01-01"
    model_subdir.mkdir()

    (model_subdir / "model.onnx").write_bytes(b"fake_onnx")
    (model_subdir / "metadata.json").write_text(json.dumps(make_metadata()))
    (model_subdir / "scaler.json").write_text(json.dumps(make_scaler_data()))
    (model_subdir / "label_encoders.json").write_text(json.dumps(make_encoders_data()))

    # Patcher DANS le namespace du module qui les utilise (evite les problemes de cache)
    with patch("soongo_data.utils.eligibility_electrif_predict.model_predict.get_most_recent_s3_model_name", return_value="model_2024-01-01"), \
         patch("soongo_data.utils.eligibility_electrif_predict.model_predict.pull_folder_from_s3"), \
         patch("soongo_data.utils.eligibility_electrif_predict.model_predict.logger", MagicMock()), \
         patch("onnxruntime.InferenceSession", return_value=MagicMock()):
        from soongo_data.utils.eligibility_electrif_predict.model_predict import ElectrificationModel
        cfg = {**CONFIG, "models_dir": str(tmp_path)}
        m = ElectrificationModel(config=cfg)

    return m


# ── __init__ ──────────────────────────────────────────────────────────────────

def test_init_model_type_loaded(model):
    assert model.model_type == "random_forest"

def test_init_feature_names_loaded(model):
    assert model.feature_names == ["age", "mileage", "energy_type"]

def test_init_categorical_features_loaded(model):
    assert "energy_type" in model.categorical_features

def test_init_numeric_features_loaded(model):
    assert "age" in model.numeric_features

def test_init_scaler_loaded(model):
    assert model.scaler is not None

def test_init_label_encoders_loaded(model):
    assert "energy_type" in model.label_encoders

def test_init_median_values_loaded(model):
    assert model.median_values_ is not None


# ── load_model_artifacts ──────────────────────────────────────────────────────

def test_load_artifacts_raises_if_dir_missing(model, tmp_path):
    with pytest.raises(FileNotFoundError):
        model.load_model_artifacts(tmp_path / "nonexistent")

def test_load_artifacts_raises_if_no_onnx(model, tmp_path):
    empty_dir = tmp_path / "empty_model"
    empty_dir.mkdir()
    (empty_dir / "metadata.json").write_text(json.dumps(make_metadata()))
    with pytest.raises(FileNotFoundError):
        model.load_model_artifacts(empty_dir)

def test_load_artifacts_raises_if_no_metadata(model, tmp_path):
    no_meta_dir = tmp_path / "no_meta"
    no_meta_dir.mkdir()
    (no_meta_dir / "model.onnx").write_bytes(b"fake")
    with patch("onnxruntime.InferenceSession"):
        with pytest.raises(FileNotFoundError):
            model.load_model_artifacts(no_meta_dir)


# ── preprocess_features ───────────────────────────────────────────────────────

def test_preprocess_returns_numpy_array(model):
    df = make_df()
    X = model.preprocess_features(df, ["age", "mileage", "energy_type"])
    assert isinstance(X, np.ndarray)

def test_preprocess_output_shape(model):
    df = make_df()
    X = model.preprocess_features(df, ["age", "mileage", "energy_type"])
    assert X.shape == (len(df), 3)

def test_preprocess_no_nan(model):
    df = make_df()
    df.loc[0, "age"] = np.nan
    X = model.preprocess_features(df, ["age", "mileage", "energy_type"])
    assert not np.any(np.isnan(X))

def test_preprocess_no_inf(model):
    df = make_df()
    df.loc[0, "mileage"] = np.inf
    X = model.preprocess_features(df, ["age", "mileage", "energy_type"])
    assert np.all(np.isfinite(X))

def test_preprocess_unseen_category_handled(model):
    df = make_df()
    df["energy_type"] = "HYDROGEN"
    X = model.preprocess_features(df, ["age", "mileage", "energy_type"])
    assert X is not None


# ── predict_proba ─────────────────────────────────────────────────────────────

def test_predict_proba_raises_if_model_none(model):
    model.model = None
    with pytest.raises(ValueError, match="Model not trained"):
        model.predict_proba(make_df())

def test_predict_proba_returns_array(model):
    df = make_df()
    fake_proba = np.random.uniform(0, 1, (len(df), 2)).astype(np.float32)
    model.model.run.return_value = [np.zeros(len(df)), fake_proba]
    model.model.get_inputs.return_value = [MagicMock(name="float_input")]
    result = model.predict_proba(df)
    assert isinstance(result, np.ndarray)

def test_predict_proba_shape(model):
    df = make_df()
    fake_proba = np.random.uniform(0, 1, (len(df), 2)).astype(np.float32)
    model.model.run.return_value = [np.zeros(len(df)), fake_proba]
    model.model.get_inputs.return_value = [MagicMock(name="float_input")]
    result = model.predict_proba(df)
    assert result.shape == (len(df),)

def test_predict_proba_values_between_0_and_1(model):
    df = make_df()
    fake_proba = np.random.uniform(0, 1, (len(df), 2)).astype(np.float32)
    model.model.run.return_value = [np.zeros(len(df)), fake_proba]
    model.model.get_inputs.return_value = [MagicMock(name="float_input")]
    result = model.predict_proba(df)
    assert np.all(result >= 0) and np.all(result <= 1)


# ── predict_score ─────────────────────────────────────────────────────────────

def test_predict_score_between_0_and_100(model):
    df = make_df()
    fake_proba = np.random.uniform(0, 1, (len(df), 2)).astype(np.float32)
    model.model.run.return_value = [np.zeros(len(df)), fake_proba]
    model.model.get_inputs.return_value = [MagicMock(name="float_input")]
    result = model.predict_score(df)
    assert np.all(result >= 0) and np.all(result <= 100)

def test_predict_score_equals_proba_times_100(model):
    df = make_df()
    fake_proba = np.random.uniform(0, 1, (len(df), 2)).astype(np.float32)
    model.model.run.return_value = [np.zeros(len(df)), fake_proba]
    model.model.get_inputs.return_value = [MagicMock(name="float_input")]
    proba = model.predict_proba(df)
    model.model.run.return_value = [np.zeros(len(df)), fake_proba]
    scores = model.predict_score(df)
    np.testing.assert_array_almost_equal(scores, proba * 100)


# ── remove_model_folder_from_local ────────────────────────────────────────────

def test_remove_folder_deletes_it(model, tmp_path):
    folder = tmp_path / "to_delete"
    folder.mkdir()
    (folder / "file.txt").write_text("x")
    model.config = {**model.config, "models_dir": str(folder)}
    model.remove_model_folder_from_local()
    assert not folder.exists()

def test_remove_folder_no_error_if_missing(model, tmp_path):
    model.config = {**model.config, "models_dir": str(tmp_path / "nonexistent")}
    model.remove_model_folder_from_local()  # ne doit pas lever d'exception