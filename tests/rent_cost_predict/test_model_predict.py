# ===================== test_model_predict.py =====================
"""
Tests unitaires pour model_predict.py (rent)
"""

import json
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

from soongo_data.utils.rent_cost_predict.model_predict import RentalCostPredictor

MODULE = 'soongo_data.utils.rent_cost_predict.model_predict'

FEATURES = ["brand", "year", "mileage"]


# ----------------------------------------------------------------------
# HELPERS / FIXTURES
# ----------------------------------------------------------------------

@pytest.fixture
def mock_config(tmp_path):
    return {"bucket_name": "test-bucket", "model_folder": "models",
            "models_dir": str(tmp_path / "models")}


@pytest.fixture
def sample_features():
    return pd.DataFrame({
        'brand': ['Toyota', 'Ford', 'Honda'],
        'year': [2020, 2019, 2021],
        'mileage': [10000, 20000, 5000],
    })


def base_metadata(**over):
    meta = {
        "model_type": "hist_gradient_boosting",
        "format": "onnx",
        "target_transform": "none",
        "feature_names": FEATURES,
        "categorical_features": ["brand"],
        "numeric_features": ["year", "mileage"],
        "metrics": {"cv_mae_mean": 10.5},
        "median_values": {"year": 2020.0, "mileage": 12000.0},
    }
    meta.update(over)
    return meta


def make_dir(tmp_path, metadata=None, scaler=True, encoders=True, files=()):
    d = tmp_path / "model_dir"
    d.mkdir(exist_ok=True)
    if metadata is not None:
        (d / "metadata.json").write_text(json.dumps(metadata))
    if scaler:
        (d / "scaler.json").write_text(json.dumps({
            "scaler_type": "StandardScaler",
            "mean": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0], "var": [1.0, 1.0, 1.0],
            "with_mean": True, "with_std": True, "n_features": 3,
        }))
    if encoders:
        (d / "label_encoders.json").write_text(json.dumps(
            {"brand": {"classes": ["Ford", "Toyota", "unknown"]}}))
    for f in files:
        (d / f).write_text("x")
    return d


def bare_predictor(**attrs):
    """Predictor sans passer par __init__ (pas de S3)."""
    with patch.object(RentalCostPredictor, '__init__', lambda self, c: None):
        p = RentalCostPredictor(None)
    defaults = dict(
        model=None, model_format="onnx", feature_names=FEATURES,
        categorical_features=["brand"], numeric_features=["year", "mileage"],
        median_values_={"year": 2020.0, "mileage": 12000.0},
        target_transform="none", blend_members=[], scaler=None, label_encoders=None,
    )
    defaults.update(attrs)
    for k, v in defaults.items():
        setattr(p, k, v)
    return p


def loaded_preprocessing(tmp_path):
    """Predictor dont scaler/encoders sont chargés depuis de vrais fichiers JSON."""
    d = make_dir(tmp_path, base_metadata())
    p = bare_predictor()
    p._load_preprocessing(d)
    return p


# ----------------------------------------------------------------------
# INIT / S3
# ----------------------------------------------------------------------

class TestInitAndS3:

    @patch(f'{MODULE}.pull_folder_from_s3')
    @patch(f'{MODULE}.s3_get_most_recent_folder', return_value="model_2024-01-01")
    def test_load_model_from_s3(self, mock_recent, mock_pull, mock_config):
        p = bare_predictor()
        p.config = mock_config

        path = p.load_model_from_s3()

        assert path == Path(mock_config["models_dir"]) / "model_2024-01-01"
        mock_recent.assert_called_once_with(bucket_name="test-bucket", prefix="models")
        mock_pull.assert_called_once_with(
            s3_prefix="models/model_2024-01-01",
            local_dir=str(path),
            bucket_name="test-bucket",
        )

    @patch.object(RentalCostPredictor, 'load_model_artifacts')
    @patch.object(RentalCostPredictor, 'load_model_from_s3', return_value=Path("/x/model"))
    def test_init_loads_artifacts_from_s3_path(self, mock_s3, mock_load, mock_config):
        p = RentalCostPredictor(mock_config)

        mock_load.assert_called_once_with(Path("/x/model"))
        assert p.config == mock_config
        assert p.target_transform == 'none'
        assert p.blend_members == []
        assert p.model_local_path == Path("/x/model")


# ----------------------------------------------------------------------
# LOAD ARTIFACTS
# ----------------------------------------------------------------------

class TestLoadArtifacts:

    def test_missing_directory(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="directory"):
            bare_predictor().load_model_artifacts(tmp_path / "nope")

    def test_missing_metadata(self, tmp_path):
        d = make_dir(tmp_path, metadata=None)
        with pytest.raises(FileNotFoundError, match="Metadata"):
            bare_predictor().load_model_artifacts(d)

    @patch(f'{MODULE}.ort.InferenceSession')
    def test_onnx_success(self, mock_ort, tmp_path):
        d = make_dir(tmp_path, base_metadata(median_values={"year": 2020.0}), files=["model.onnx"])
        p = bare_predictor()

        p.load_model_artifacts(d)

        assert p.model_type == "hist_gradient_boosting"
        assert p.model_format == "onnx"
        assert p.feature_names == FEATURES
        assert p.categorical_features == ["brand"]
        assert p.median_values_ == {"year": 2020.0}
        assert p.target_transform == "none"
        assert p.scaler is not None
        assert "brand" in p.label_encoders
        mock_ort.assert_called_once_with(str(d / "model.onnx"))

    def test_onnx_model_file_missing(self, tmp_path):
        d = make_dir(tmp_path, base_metadata())
        with pytest.raises(FileNotFoundError, match="ONNX"):
            bare_predictor().load_model_artifacts(d)

    @patch(f'{MODULE}.ort.InferenceSession')
    def test_format_defaults_to_onnx(self, mock_ort, tmp_path):
        meta = base_metadata()
        del meta["format"]
        d = make_dir(tmp_path, meta, files=["model.onnx"])
        p = bare_predictor()
        p.load_model_artifacts(d)
        assert p.model_format == "onnx"

    @patch(f'{MODULE}.ort.InferenceSession')
    def test_target_transform_read_from_metadata(self, mock_ort, tmp_path):
        d = make_dir(tmp_path, base_metadata(target_transform="log"), files=["model.onnx"])
        p = bare_predictor()
        p.load_model_artifacts(d)
        assert p.target_transform == "log"

    @patch(f'{MODULE}.ort.InferenceSession')
    def test_missing_scaler_and_encoders_set_none(self, mock_ort, tmp_path):
        d = make_dir(tmp_path, base_metadata(), scaler=False, encoders=False, files=["model.onnx"])
        p = bare_predictor()
        p.load_model_artifacts(d)
        assert p.scaler is None
        assert p.label_encoders is None

    def test_scaler_values_restored(self, tmp_path):
        p = loaded_preprocessing(tmp_path)
        assert list(p.scaler.scale_) == [1.0, 1.0, 1.0]
        assert p.scaler.n_features_in_ == 3
        assert p.scaler.with_mean is True

    def test_encoder_classes_restored_and_unknown_is_minus_one(self, tmp_path):
        p = loaded_preprocessing(tmp_path)
        enc = p.label_encoders['brand']
        assert list(enc.categories_[0]) == ["Ford", "Toyota", "unknown"]
        assert enc.transform(pd.DataFrame({'brand': ['Zzz']}))[0][0] == -1

    def test_catboost(self, tmp_path):
        pytest.importorskip("catboost")
        meta = base_metadata(model_type="catboost", format="cbm")
        d = make_dir(tmp_path, meta, scaler=False, encoders=False, files=["model.cbm"])
        p = bare_predictor()

        with patch('catboost.CatBoostRegressor') as cls:
            p.load_model_artifacts(d)

        assert p.model_format == "cbm"
        assert p.scaler is None and p.label_encoders is None
        cls.return_value.load_model.assert_called_once_with(str(d / "model.cbm"), format="cbm")

    def test_catboost_file_missing(self, tmp_path):
        pytest.importorskip("catboost")
        d = make_dir(tmp_path, base_metadata(format="cbm"), scaler=False, encoders=False)
        with pytest.raises(FileNotFoundError, match="CatBoost"):
            bare_predictor().load_model_artifacts(d)

    @patch(f'{MODULE}.ort.InferenceSession')
    def test_blend_success(self, mock_ort, tmp_path):
        members = [
            {"name": "hist_gradient_boosting", "file": "a.onnx", "weight": 1.0},
            {"name": "extra_trees", "file": "b.onnx", "weight": 2.0},
        ]
        d = make_dir(tmp_path, base_metadata(format="onnx_blend", model_type="blend",
                                             blend_members=members), files=["a.onnx", "b.onnx"])
        p = bare_predictor()

        p.load_model_artifacts(d)

        assert [m[0] for m in p.blend_members] == ["hist_gradient_boosting", "extra_trees"]
        assert [m[2] for m in p.blend_members] == [1.0, 2.0]
        assert p.model is p.blend_members
        assert mock_ort.call_count == 2
        assert p.scaler is not None

    def test_blend_without_members_metadata(self, tmp_path):
        d = make_dir(tmp_path, base_metadata(format="onnx_blend"))
        with pytest.raises(ValueError, match="blend_members"):
            bare_predictor().load_model_artifacts(d)

    @patch(f'{MODULE}.ort.InferenceSession')
    def test_blend_member_file_missing(self, mock_ort, tmp_path):
        members = [{"name": "extra_trees", "file": "missing.onnx"}]
        d = make_dir(tmp_path, base_metadata(format="onnx_blend", blend_members=members))
        with pytest.raises(FileNotFoundError, match="Blend member"):
            bare_predictor().load_model_artifacts(d)

    @patch(f'{MODULE}.ort.InferenceSession')
    def test_blend_weight_defaults_to_one(self, mock_ort, tmp_path):
        members = [{"name": "extra_trees", "file": "a.onnx"}]
        d = make_dir(tmp_path, base_metadata(format="onnx_blend", blend_members=members), files=["a.onnx"])
        p = bare_predictor()
        p.load_model_artifacts(d)
        assert p.blend_members[0][2] == 1.0


# ----------------------------------------------------------------------
# CLEANUP
# ----------------------------------------------------------------------

class TestCleanup:

    @patch('shutil.rmtree')
    def test_remove_model_folder(self, mock_rmtree, mock_config):
        p = bare_predictor()
        p.config = mock_config
        p.remove_model_folder_from_local()
        mock_rmtree.assert_called_once_with(Path(mock_config["models_dir"]))

    @patch('shutil.rmtree', side_effect=OSError("denied"))
    def test_remove_model_folder_swallows_errors(self, mock_rmtree, mock_config):
        p = bare_predictor()
        p.config = mock_config
        p.remove_model_folder_from_local()


# ----------------------------------------------------------------------
# PREPROCESS
# ----------------------------------------------------------------------

class TestPreprocess:

    def test_encodes_and_scales(self, tmp_path, sample_features):
        p = loaded_preprocessing(tmp_path)

        X = p.preprocess_features(sample_features, FEATURES)

        # brand: Ford=0, Toyota=1 ; Honda inconnu -> 'unknown' (=2, présent au train)
        assert X.shape == (3, 3)
        assert list(X[:, 0]) == [1.0, 0.0, 2.0]
        assert list(X[:, 1]) == [2020.0, 2019.0, 2021.0]

    def test_unknown_category_maps_to_unknown_when_learned(self, tmp_path):
        p = loaded_preprocessing(tmp_path)
        df = pd.DataFrame({'brand': ['NewBrand'], 'year': [2020], 'mileage': [1]})
        assert p.preprocess_features(df, FEATURES)[0, 0] == 2.0

    def test_unknown_category_minus_one_when_not_learned(self, tmp_path):
        p = loaded_preprocessing(tmp_path)
        (tmp_path / "model_dir" / "label_encoders.json").write_text(
            json.dumps({"brand": {"classes": ["Ford", "Toyota"]}}))
        p._load_preprocessing(tmp_path / "model_dir")
        df = pd.DataFrame({'brand': ['NewBrand'], 'year': [2020], 'mileage': [1]})
        assert p.preprocess_features(df, FEATURES)[0, 0] == -1

    def test_nan_category_becomes_unknown(self, tmp_path):
        p = loaded_preprocessing(tmp_path)
        df = pd.DataFrame({'brand': [None], 'year': [2020], 'mileage': [1]})
        assert p.preprocess_features(df, FEATURES)[0, 0] == 2.0

    def test_numeric_nan_and_inf_use_train_median(self, tmp_path):
        p = loaded_preprocessing(tmp_path)
        df = pd.DataFrame({'brand': ['Ford', 'Ford'], 'year': [np.nan, 2019],
                           'mileage': [np.inf, -np.inf]})

        X = p.preprocess_features(df, FEATURES)

        assert X[0, 1] == 2020.0
        assert list(X[:, 2]) == [12000.0, 12000.0]

    def test_numeric_strings_coerced(self, tmp_path):
        p = loaded_preprocessing(tmp_path)
        df = pd.DataFrame({'brand': ['Ford'], 'year': ['abc'], 'mileage': ['5000']})
        X = p.preprocess_features(df, FEATURES)
        assert X[0, 1] == 2020.0 and X[0, 2] == 5000.0

    def test_missing_median_fills_zero(self, tmp_path):
        p = loaded_preprocessing(tmp_path)
        p.median_values_ = {}
        df = pd.DataFrame({'brand': ['Ford'], 'year': [np.nan], 'mileage': [1]})
        assert p.preprocess_features(df, FEATURES)[0, 1] == 0.0

    def test_column_order_follows_feature_list(self, tmp_path, sample_features):
        p = loaded_preprocessing(tmp_path)
        shuffled = sample_features[['mileage', 'brand', 'year']]
        X = p.preprocess_features(shuffled, FEATURES)
        assert list(X[:, 2]) == [10000.0, 20000.0, 5000.0]

    def test_input_not_mutated(self, tmp_path, sample_features):
        p = loaded_preprocessing(tmp_path)
        before = sample_features.copy()
        p.preprocess_features(sample_features, FEATURES)
        pd.testing.assert_frame_equal(sample_features, before)


# ----------------------------------------------------------------------
# INVERSE TARGET
# ----------------------------------------------------------------------

class TestInverseTarget:

    def test_none(self):
        p = bare_predictor(target_transform='none')
        assert np.allclose(p._inverse_target(np.array([100.0]), pd.DataFrame()), [100.0])

    def test_log(self):
        p = bare_predictor(target_transform='log')
        assert np.allclose(p._inverse_target(np.log1p(np.array([100.0, 250.0])), pd.DataFrame()),
                           [100.0, 250.0])

    def test_monthly_log(self):
        p = bare_predictor(target_transform='monthly_log')
        X = pd.DataFrame({'lease_months': [12, 24]})
        pred = np.log1p(np.array([100.0, 200.0]))
        assert np.allclose(p._inverse_target(pred, X), [1200.0, 4800.0])

    def test_monthly_log_clips_months_to_one(self):
        p = bare_predictor(target_transform='monthly_log')
        X = pd.DataFrame({'lease_months': [0]})
        assert np.allclose(p._inverse_target(np.log1p(np.array([100.0])), X), [100.0])

    def test_unknown_transform_raises(self):
        p = bare_predictor(target_transform='sqrt')
        with pytest.raises(ValueError, match="inconnu"):
            p._inverse_target(np.array([1.0]), pd.DataFrame())

    def test_negative_clipped_to_zero(self):
        p = bare_predictor(target_transform='none')
        assert list(p._inverse_target(np.array([-50.0, 20.0]), pd.DataFrame())) == [0.0, 20.0]

    def test_none_transform_attribute_defaults(self):
        p = bare_predictor(target_transform=None)
        assert np.allclose(p._inverse_target(np.array([5.0]), pd.DataFrame()), [5.0])


# ----------------------------------------------------------------------
# PREDICT
# ----------------------------------------------------------------------

class TestPredict:

    def test_model_not_loaded(self, sample_features):
        with pytest.raises(ValueError, match="not loaded"):
            bare_predictor(model=None).predict(sample_features)

    def test_dispatch_onnx(self, sample_features):
        p = bare_predictor(model=MagicMock(), model_format="onnx")
        p._predict_onnx = MagicMock(return_value=np.array([1.0]))
        p._predict_catboost = MagicMock()
        p._predict_onnx_blend = MagicMock()

        p.predict(sample_features)

        p._predict_onnx.assert_called_once()
        p._predict_catboost.assert_not_called()
        p._predict_onnx_blend.assert_not_called()

    def test_dispatch_catboost(self, sample_features):
        p = bare_predictor(model=MagicMock(), model_format="cbm")
        p._predict_onnx = MagicMock()
        p._predict_catboost = MagicMock(return_value=np.array([1.0]))

        p.predict(sample_features)

        p._predict_catboost.assert_called_once()
        p._predict_onnx.assert_not_called()

    def test_dispatch_blend(self, sample_features):
        p = bare_predictor(model=MagicMock(), model_format="onnx_blend")
        p._predict_onnx = MagicMock()
        p._predict_onnx_blend = MagicMock(return_value=np.array([1.0]))

        p.predict(sample_features)

        p._predict_onnx_blend.assert_called_once()
        p._predict_onnx.assert_not_called()

    def test_predict_applies_inverse_transform(self, sample_features):
        p = bare_predictor(model=MagicMock(), model_format="onnx", target_transform="log")
        p._predict_onnx = MagicMock(return_value=np.log1p(np.array([100.0, 200.0, 300.0])))

        assert np.allclose(p.predict(sample_features), [100.0, 200.0, 300.0])

    def test_predict_never_negative(self, sample_features):
        p = bare_predictor(model=MagicMock(), model_format="onnx")
        p._predict_onnx = MagicMock(return_value=np.array([-10.0, 5.0, 7.0]))
        assert (p.predict(sample_features) >= 0).all()

    # ---- ONNX ----

    def test_predict_onnx(self, sample_features):
        session = MagicMock()
        session.get_inputs.return_value = [MagicMock()]
        session.get_inputs.return_value[0].name = "float_input"
        session.run.return_value = [np.array([[500.0], [600.0], [550.0]])]
        p = bare_predictor(model=session, model_format="onnx")
        p.preprocess_features = MagicMock(return_value=np.ones((3, 3)))

        result = p.predict(sample_features)

        assert list(result) == [500.0, 600.0, 550.0]
        feed = session.run.call_args[0][1]
        assert list(feed) == ["float_input"]
        assert feed["float_input"].dtype == np.float32

    def test_predict_onnx_error(self, sample_features):
        session = MagicMock()
        session.run.side_effect = Exception("ONNX error")
        p = bare_predictor(model=session, model_format="onnx")
        p.preprocess_features = MagicMock(return_value=np.ones((3, 3)))

        with pytest.raises(Exception, match="ONNX error"):
            p.predict(sample_features)

    # ---- BLEND ----

    @staticmethod
    def _session(values, name="float_input"):
        s = MagicMock()
        inp = MagicMock()
        inp.name = name
        s.get_inputs.return_value = [inp]
        s.run.return_value = [np.array(values).reshape(-1, 1)]
        return s

    def test_predict_blend_equal_weights(self, sample_features):
        members = [("a", self._session([100, 200, 300]), 1.0),
                   ("b", self._session([300, 400, 500]), 1.0)]
        p = bare_predictor(model=members, model_format="onnx_blend", blend_members=members)
        p.preprocess_features = MagicMock(return_value=np.ones((3, 3)))

        assert np.allclose(p.predict(sample_features), [200.0, 300.0, 400.0])

    def test_predict_blend_weighted(self, sample_features):
        members = [("a", self._session([100, 100, 100]), 1.0),
                   ("b", self._session([400, 400, 400]), 2.0)]
        p = bare_predictor(model=members, model_format="onnx_blend", blend_members=members)
        p.preprocess_features = MagicMock(return_value=np.ones((3, 3)))

        assert np.allclose(p.predict(sample_features), [300.0] * 3)

    def test_blend_preprocesses_once(self, sample_features):
        members = [("a", self._session([1, 1, 1]), 1.0), ("b", self._session([1, 1, 1]), 1.0)]
        p = bare_predictor(model=members, model_format="onnx_blend", blend_members=members)
        p.preprocess_features = MagicMock(return_value=np.ones((3, 3)))

        p.predict(sample_features)

        p.preprocess_features.assert_called_once()

    def test_blend_member_error_propagates(self, sample_features):
        bad = self._session([1, 1, 1])
        bad.run.side_effect = Exception("member down")
        members = [("a", bad, 1.0)]
        p = bare_predictor(model=members, model_format="onnx_blend", blend_members=members)
        p.preprocess_features = MagicMock(return_value=np.ones((3, 3)))

        with pytest.raises(Exception, match="member down"):
            p.predict(sample_features)

    # ---- CATBOOST ----

    def test_predict_catboost(self, sample_features):
        pytest.importorskip("catboost")
        model = MagicMock()
        model.predict.return_value = np.array([500.0, 600.0, 550.0])
        p = bare_predictor(model=model, model_format="cbm")

        with patch('catboost.Pool') as pool_cls:
            result = p.predict(sample_features)

        assert list(result) == [500.0, 600.0, 550.0]
        _, kwargs = pool_cls.call_args
        assert kwargs['cat_features'] == [0]       # index de 'brand'

    def test_catboost_reorders_columns_and_fills_unknown(self):
        pytest.importorskip("catboost")
        model = MagicMock()
        model.predict.return_value = np.array([1.0, 2.0])
        p = bare_predictor(model=model, model_format="cbm")
        df = pd.DataFrame({'mileage': [1, 2], 'brand': [None, 'Ford'], 'year': [2020, 2021]})

        with patch('catboost.Pool') as pool_cls:
            p.predict(df)

        pool_df = pool_cls.call_args[0][0]
        assert list(pool_df.columns) == FEATURES
        assert list(pool_df['brand']) == ['unknown', 'Ford']