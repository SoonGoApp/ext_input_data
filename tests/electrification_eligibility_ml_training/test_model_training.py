import os
import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch


# ── helpers ───

CONFIG = {
    "model_type": "random_forest",
    "model_params": {"n_estimators": 10, "max_depth": 3, "random_state": 42},
    "test_size": 0.3,
    "random_state": 42,
    "models_dir": "/tmp/test_models",
    "bucket_name": "test-bucket",
}

def make_df(n=100):
    """DataFrame simple avec features numériques et catégorielles."""
    np.random.seed(42)
    return pd.DataFrame({
        "age":         np.random.uniform(0, 10, n),
        "mileage":     np.random.uniform(0, 500, n),
        "fuel_amount": np.random.uniform(0, 200, n),
        "energy_type": np.random.choice(["DIESEL", "PETROL", "ELECTRIC"], n),
    })

def make_target(n=100):
    np.random.seed(42)
    return pd.Series(np.random.randint(0, 2, n), name="target")

def make_model():
    with patch("soongo_data.utils.logging_utils.gen_logger", return_value=MagicMock()), \
         patch("soongo_data.utils.aws.push_folder_to_s3"):
        from soongo_data.utils.eligibility_electrif_training.model_training import ElectrificationModel
        return ElectrificationModel(config=CONFIG)

@pytest.fixture
def model():
    return make_model()

@pytest.fixture
def trained_model():
    m = make_model()
    df = make_df()
    y  = make_target()
    m.train(df, y, feature_list=df.columns.tolist())
    return m


# ── __init__ ───

def test_init_model_is_none(model):
    assert model.model is None

def test_init_threshold(model):
    assert model.threshold == 0.55

def test_init_model_type(model):
    assert model.model_type == "random_forest"

def test_init_feature_names_none(model):
    assert model.feature_names is None


# ── _get_model ───

def test_get_model_returns_random_forest(model):
    from sklearn.ensemble import RandomForestClassifier
    clf = model._get_model()
    assert isinstance(clf, RandomForestClassifier)

def test_get_model_params_applied(model):
    clf = model._get_model()
    assert clf.n_estimators == 10
    assert clf.max_depth == 3


# ── preprocess_features ────

def test_preprocess_returns_numpy_array(model):
    df = make_df()
    X = model.preprocess_features(df, df.columns.tolist(), fit=True)
    assert isinstance(X, np.ndarray)

def test_preprocess_output_shape(model):
    df = make_df()
    X = model.preprocess_features(df, df.columns.tolist(), fit=True)
    assert X.shape == (len(df), len(df.columns))

def test_preprocess_no_nan_in_output(model):
    df = make_df()
    df.loc[0, "age"] = np.nan  # inject NaN
    X = model.preprocess_features(df, df.columns.tolist(), fit=True)
    assert not np.any(np.isnan(X))

def test_preprocess_no_inf_in_output(model):
    df = make_df()
    df.loc[0, "mileage"] = np.inf  # inject inf
    X = model.preprocess_features(df, df.columns.tolist(), fit=True)
    assert np.all(np.isfinite(X))

def test_preprocess_detects_categorical(model):
    df = make_df()
    model.preprocess_features(df, df.columns.tolist(), fit=True)
    assert "energy_type" in model.categorical_features

def test_preprocess_detects_numeric(model):
    df = make_df()
    model.preprocess_features(df, df.columns.tolist(), fit=True)
    assert "age" in model.numeric_features


# ── train ───

def test_train_sets_model(model):
    df = make_df()
    y  = make_target()
    model.train(df, y, feature_list=df.columns.tolist())
    assert model.model is not None

def test_train_returns_dict(model):
    df = make_df()
    y  = make_target()
    metrics = model.train(df, y, feature_list=df.columns.tolist())
    assert isinstance(metrics, dict)

def test_train_metrics_has_auc(model):
    df = make_df()
    y  = make_target()
    metrics = model.train(df, y, feature_list=df.columns.tolist())
    assert "train_auc" in metrics

def test_train_auc_between_0_and_1(model):
    df = make_df()
    y  = make_target()
    metrics = model.train(df, y, feature_list=df.columns.tolist())
    assert 0.0 <= metrics["train_auc"] <= 1.0

def test_train_stores_feature_names(model):
    df = make_df()
    y  = make_target()
    model.train(df, y, feature_list=df.columns.tolist())
    assert model.feature_names == df.columns.tolist()


# ── predict_proba ───

def test_predict_proba_raises_if_not_trained(model):
    model.feature_names = make_df().columns.tolist()
    with pytest.raises(ValueError, match="Model not trained"):
        model.predict_proba(make_df())

def test_predict_proba_shape(trained_model):
    df = make_df()
    result = trained_model.predict_proba(df)
    assert result.shape == (len(df),)

def test_predict_proba_values_between_0_and_1(trained_model):
    result = trained_model.predict_proba(make_df())
    assert np.all(result >= 0) and np.all(result <= 1)


# ── predict_score ───

def test_predict_score_between_0_and_100(trained_model):
    result = trained_model.predict_score(make_df())
    assert np.all(result >= 0) and np.all(result <= 100)

def test_predict_score_equals_proba_times_100(trained_model):
    df = make_df()
    proba  = trained_model.predict_proba(df)
    scores = trained_model.predict_score(df)
    np.testing.assert_array_almost_equal(scores, proba * 100)


# ── evaluate ───

def test_evaluate_returns_dict(trained_model):
    result = trained_model.evaluate(make_df(), make_target())
    assert isinstance(result, dict)

def test_evaluate_has_test_auc(trained_model):
    result = trained_model.evaluate(make_df(), make_target())
    assert "test_auc" in result

def test_evaluate_auc_between_0_and_1(trained_model):
    result = trained_model.evaluate(make_df(), make_target())
    assert 0.0 <= result["test_auc"] <= 1.0

def test_evaluate_has_confusion_matrix(trained_model):
    result = trained_model.evaluate(make_df(), make_target())
    assert "confusion_matrix" in result


# ── get_feature_importance ───

def test_feature_importance_raises_if_not_trained(model):
    with pytest.raises(ValueError, match="Model not trained"):
        model.get_feature_importance()

def test_feature_importance_returns_dataframe(trained_model):
    df = trained_model.get_feature_importance()
    assert isinstance(df, pd.DataFrame)

def test_feature_importance_has_columns(trained_model):
    df = trained_model.get_feature_importance()
    assert "feature" in df.columns
    assert "importance" in df.columns


# ── prepare_train_test_split ───

def test_split_returns_4_elements(model):
    features = make_df()
    features.insert(0, "vehicle_id", [f"V{i}" for i in range(len(features))])
    target = pd.DataFrame({"vehicle_id": features["vehicle_id"], "target": make_target()})
    result = model.prepare_train_test_split(features, target)
    assert len(result) == 4

def test_split_vehicle_id_not_in_features(model):
    features = make_df()
    features.insert(0, "vehicle_id", [f"V{i}" for i in range(len(features))])
    target = pd.DataFrame({"vehicle_id": features["vehicle_id"], "target": make_target()})
    X_train, X_test, _, _ = model.prepare_train_test_split(features, target)
    assert "vehicle_id" not in X_train.columns
    assert "vehicle_id" not in X_test.columns

def test_split_correct_sizes(model):
    features = make_df()
    features.insert(0, "vehicle_id", [f"V{i}" for i in range(len(features))])
    target = pd.DataFrame({"vehicle_id": features["vehicle_id"], "target": make_target()})
    X_train, X_test, _, _ = model.prepare_train_test_split(features, target, test_size=0.3)
    assert len(X_test) == 30
    assert len(X_train) == 70


# ── remove_model_folder_from_local ────

def test_remove_folder_deletes_it(tmp_path):
    folder = tmp_path / "models"
    folder.mkdir()
    (folder / "file.txt").write_text("x")
    cfg = {**CONFIG, "models_dir": str(folder)}
    m = make_model()
    m.config = cfg
    m.remove_model_folder_from_local()
    assert not folder.exists()

def test_remove_folder_no_error_if_missing(tmp_path):
    cfg = {**CONFIG, "models_dir": str(tmp_path / "nonexistent")}
    m = make_model()
    m.config = cfg
    m.remove_model_folder_from_local()  # ne doit pas lever d'exception