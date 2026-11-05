"""
Tests unitaires pour model_training.py (RentCostModel / BlendRegressor)
"""

import json
import sys
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

from soongo_data.utils.rent_cost_training.model_training import (
    RentCostModel,
    BlendRegressor,
    GROUP_COLS,
    NON_FEATURE_COLS,
)

MODULE = 'soongo_data.utils.rent_cost_training.model_training'


# ----------------------------------------------------------------------
# FIXTURES
# ----------------------------------------------------------------------

@pytest.fixture
def mock_config(tmp_path):
    return {
        "model_type": "hist_gradient_boosting",
        "test_size": 0.3,
        "random_state": 42,
        "models_dir": str(tmp_path / "models"),
        "bucket_name": "test-bucket",
        "use_optuna": False,
        "use_shap": False,
        "model_params": {"max_iter": 20, "random_state": 42},
    }


@pytest.fixture
def blend_config(mock_config):
    return {
        **mock_config,
        "model_type": "blend",
        "model_params": {
            "blend_members": {
                "hist_gradient_boosting": {"max_iter": 10, "random_state": 0},
                "extra_trees": {"n_estimators": 5, "random_state": 0},
            }
        },
    }


@pytest.fixture
def rent_data():
    """30 lignes, 10 modèles (brand|model) de 3 véhicules chacun."""
    rng = np.random.RandomState(0)
    brands = ['Toyota', 'Ford', 'Honda', 'Fiat', 'Audi']
    rows = []
    for g in range(10):
        brand = brands[g % 5]
        model = f"M{g}"
        base = 300 + 40 * g
        for k in range(3):
            rows.append({
                'vehicle_id': f"v{g}_{k}",
                'brand': brand,
                'model': model,
                'segment': 'SUV' if g % 2 else 'CITY',
                'lease_months': 36,
                'mileage': float(10000 + 1000 * k + rng.randint(0, 500)),
                'label_depreciation': float(base * 0.5),
                'target': float(base + rng.randint(0, 20)),
            })
    df = pd.DataFrame(rows)
    return df.drop(columns=['target']), df[['vehicle_id', 'target']]


class FakeRegressor:
    def __init__(self, *a, **k):
        pass

    def fit(self, X, y, *a, **k):
        self.mean_ = float(np.mean(y))
        return self

    def predict(self, X):
        return np.full(len(X), self.mean_)


# ----------------------------------------------------------------------
# BLEND REGRESSOR
# ----------------------------------------------------------------------

class TestBlendRegressor:

    def _members(self):
        return [("a", FakeRegressor()), ("b", FakeRegressor())]

    def test_fit_predict_averages_members(self):
        blend = BlendRegressor(self._members())
        blend.members[0][1].fit(np.zeros((2, 1)), [0, 0])
        blend.members[1][1].fit(np.zeros((2, 1)), [0, 0])
        # on réentraîne avec des cibles différentes via fit sur le blend entier
        a, b = FakeRegressor(), FakeRegressor()
        a.fit(None, [10.0]); b.fit(None, [20.0])
        blend = BlendRegressor([("a", a), ("b", b)])

        pred = blend.predict(np.zeros((3, 2)))

        assert np.allclose(pred, 15.0)

    def test_fit_fits_all_members_and_returns_self(self):
        blend = BlendRegressor(self._members())

        out = blend.fit(pd.DataFrame({'x': [1, 2, 3]}), np.array([1.0, 2.0, 3.0]))

        assert out is blend
        assert all(hasattr(e, 'mean_') for _, e in blend.members)

    def test_named(self):
        blend = BlendRegressor(self._members())
        assert blend.named("a") is blend.members[0][1]
        assert blend.named("zzz") is None

    def test_shap_member_priority(self):
        lgbm, et, hgb = FakeRegressor(), FakeRegressor(), FakeRegressor()
        blend = BlendRegressor([("hist_gradient_boosting", hgb), ("extra_trees", et), ("lightgbm", lgbm)])
        assert blend.shap_member() is lgbm

        blend = BlendRegressor([("hist_gradient_boosting", hgb), ("extra_trees", et)])
        assert blend.shap_member() is et

        blend = BlendRegressor([("hist_gradient_boosting", hgb)])
        assert blend.shap_member() is hgb

    def test_feature_importances_mean_of_normalised(self):
        m1, m2 = MagicMock(), MagicMock()
        m1.feature_importances_ = np.array([2.0, 2.0])      # -> 0.5 / 0.5
        m2.feature_importances_ = np.array([3.0, 1.0])      # -> 0.75 / 0.25
        blend = BlendRegressor([("a", m1), ("b", m2)])

        assert np.allclose(blend.feature_importances_, [0.625, 0.375])

    def test_feature_importances_raises_when_none_available(self):
        blend = BlendRegressor([("a", MagicMock(spec=['fit', 'predict']))])
        with pytest.raises(AttributeError):
            _ = blend.feature_importances_


# ----------------------------------------------------------------------
# RentCostModel
# ----------------------------------------------------------------------

class TestInitAndFactory:

    def test_init_defaults(self, mock_config):
        model = RentCostModel(mock_config)
        assert model.model_type == "hist_gradient_boosting"
        assert model.test_size == 0.3
        assert model.random_state == 42
        assert model.model is None
        assert model.best_params is None
        assert model.target_transform == 'none'
        assert model.exclude_features == []

    def test_init_reads_target_transform_and_exclusions(self, mock_config):
        model = RentCostModel({**mock_config, "target_transform": "log",
                               "exclude_features": ["organization"]})
        assert model.target_transform == 'log'
        assert model.exclude_features == ["organization"]

    def test_get_model_default(self, mock_config):
        assert hasattr(RentCostModel(mock_config)._get_model(), 'fit')

    def test_get_model_explicit_params_override_config(self, mock_config):
        base = RentCostModel(mock_config)._get_model(params={"max_iter": 7})
        assert base.max_iter == 7

    def test_get_model_catboost(self, mock_config):
        pytest.importorskip("catboost")
        model = RentCostModel({**mock_config, "model_type": "catboost"})
        model.feature_names = ['segment', 'power']
        model.categorical_features = ['segment']
        base = model._get_model(params={"iterations": 5, "verbose": 0})
        assert base.__class__.__name__ == "CatBoostRegressor"

    def test_get_model_blend(self, blend_config):
        base = RentCostModel(blend_config)._get_model()
        assert isinstance(base, BlendRegressor)
        assert [n for n, _ in base.members] == ["hist_gradient_boosting", "extra_trees"]

    def test_build_blend_requires_members(self, mock_config):
        model = RentCostModel({**mock_config, "model_type": "blend"})
        with pytest.raises(ValueError, match="blend_members"):
            model._get_model(params={})

    def test_build_blend_unknown_member(self, mock_config):
        model = RentCostModel({**mock_config, "model_type": "blend"})
        with pytest.raises(ValueError, match="inconnu"):
            model._get_model(params={"blend_members": {"foo": {}}})


class TestFeatureColumnsAndTarget:

    def test_excluded_cols_dedup(self, mock_config):
        model = RentCostModel({**mock_config, "exclude_features": ["organization", "model"]})
        excluded = model._excluded_cols()
        assert excluded.count("model") == 1
        assert set(NON_FEATURE_COLS) <= set(excluded)
        assert "organization" in excluded

    def test_feature_columns_excludes_ids_config_and_labels(self, mock_config):
        model = RentCostModel({**mock_config, "exclude_features": ["organization"]})
        df = pd.DataFrame(columns=[
            'vehicle_id', 'brand', 'model', 'organization', 'mileage',
            'label_depreciation', 'label_insurance',
        ])
        assert model._feature_columns(df) == ['brand', 'mileage']

    def test_transform_none(self, mock_config):
        model = RentCostModel(mock_config)
        X = pd.DataFrame({'lease_months': [12, 24]})
        y = np.array([100.0, 200.0])
        assert np.allclose(model._transform_target(y, X), y)
        assert np.allclose(model._inverse_target(y, X), y)

    def test_transform_log_roundtrip(self, mock_config):
        model = RentCostModel({**mock_config, "target_transform": "log"})
        X = pd.DataFrame({'lease_months': [12, 24]})
        y = np.array([100.0, 250.0])
        assert np.allclose(model._inverse_target(model._transform_target(y, X), X), y)

    def test_transform_monthly_log_roundtrip(self, mock_config):
        model = RentCostModel({**mock_config, "target_transform": "monthly_log"})
        X = pd.DataFrame({'lease_months': [12, 24]})
        y = np.array([1200.0, 4800.0])
        assert np.allclose(model._inverse_target(model._transform_target(y, X), X), y)

    def test_monthly_log_requires_lease_months(self, mock_config):
        model = RentCostModel({**mock_config, "target_transform": "monthly_log"})
        with pytest.raises(ValueError, match="lease_months"):
            model._transform_target(np.array([1.0]), pd.DataFrame({'x': [1]}))

    def test_unknown_transform_raises(self, mock_config):
        model = RentCostModel({**mock_config, "target_transform": "sqrt"})
        X = pd.DataFrame({'lease_months': [12]})
        with pytest.raises(ValueError, match="inconnu"):
            model._transform_target(np.array([1.0]), X)
        with pytest.raises(ValueError, match="inconnu"):
            model._inverse_target(np.array([1.0]), X)


class TestCleaning:

    def test_drops_duplicate_vehicle_id_keeps_first(self):
        df = pd.DataFrame({'vehicle_id': ['v1', 'v1', 'v2'],
                           'segment': ['SUV', 'SUV', 'CITY'],
                           'target': [100, 999, 200]})
        out = RentCostModel.clean_training_data(df)
        assert len(out) == 2
        assert out.loc[out.vehicle_id == 'v1', 'target'].iloc[0] == 100

    @pytest.mark.parametrize("seg", ['unknown', 'UNKNOWN', 'SCOOTER', 'TWO_WHEEL', 'TRUCK', 'BIKE'])
    def test_filters_bad_segments(self, seg):
        df = pd.DataFrame({'vehicle_id': ['v1', 'v2'], 'segment': ['SUV', seg], 'target': [1, 2]})
        assert list(RentCostModel.clean_training_data(df)['segment']) == ['SUV']

    def test_filters_negative_target_keeps_zero(self):
        df = pd.DataFrame({'vehicle_id': ['v1', 'v2', 'v3'], 'segment': ['SUV'] * 3,
                           'target': [100, -50, 0]})
        assert list(RentCostModel.clean_training_data(df)['target']) == [100, 0]

    def test_without_optional_columns(self):
        df = pd.DataFrame({'x': [1, 2]})
        assert len(RentCostModel.clean_training_data(df)) == 2

    def test_index_reset_and_input_untouched(self):
        df = pd.DataFrame({'vehicle_id': ['v1', 'v1', 'v2'], 'segment': ['SUV'] * 3, 'target': [1, 1, 2]})
        out = RentCostModel.clean_training_data(df)
        assert list(out.index) == [0, 1]
        assert len(df) == 3


class TestGroupKey:

    def test_default_group_cols(self):
        assert GROUP_COLS == ['brand', 'model']

    def test_basic(self):
        df = pd.DataFrame({'brand': ['Toyota', 'Ford'], 'model': ['Yaris', 'Fiesta']})
        assert list(RentCostModel._build_group_key(df, GROUP_COLS)) == ['Toyota|Yaris', 'Ford|Fiesta']

    def test_nan_becomes_unknown(self):
        df = pd.DataFrame({'brand': ['Toyota', None], 'model': ['Yaris', 'X']})
        assert RentCostModel._build_group_key(df, GROUP_COLS).iloc[1] == 'unknown|X'

    def test_categorical_columns(self):
        df = pd.DataFrame({'brand': pd.Categorical(['A', None]), 'model': ['m', 'n']})
        assert list(RentCostModel._build_group_key(df, GROUP_COLS)) == ['A|m', 'unknown|n']

    def test_missing_column_raises(self):
        df = pd.DataFrame({'brand': ['Toyota']})
        with pytest.raises(ValueError, match="model"):
            RentCostModel._build_group_key(df, GROUP_COLS)

    def test_same_model_same_group(self):
        df = pd.DataFrame({'brand': ['T', 'T', 'F'], 'model': ['Y', 'Y', 'Y']})
        groups = RentCostModel._build_group_key(df, GROUP_COLS)
        assert groups.nunique() == 2 and groups.iloc[0] == groups.iloc[1]


class TestPreprocess:

    def _df(self):
        return pd.DataFrame({
            'brand': ['A', 'B', 'A', 'C'],
            'power': [100.0, np.nan, 120.0, 140.0],
            'km': [1.0, 2.0, 3.0, 4.0],
        })

    def test_fit_detects_types_and_medians(self, mock_config):
        model = RentCostModel(mock_config)
        X = model.preprocess_features(self._df(), ['brand', 'power', 'km'], fit=True)
        assert X.shape == (4, 3)
        assert model.categorical_features == ['brand']
        assert model.numeric_features == ['power', 'km']
        assert model.median_values_['power'] == 120.0
        assert not np.isnan(X).any()

    def test_transform_uses_train_median_and_unknown_category(self, mock_config):
        model = RentCostModel(mock_config)
        model.preprocess_features(self._df(), ['brand', 'power', 'km'], fit=True)
        new = pd.DataFrame({'brand': ['ZZZ'], 'power': [np.nan], 'km': [2.0]})
        X = model.preprocess_features(new, ['brand', 'power', 'km'], fit=False)
        assert X.shape == (1, 3)
        assert not np.isnan(X).any()

    def test_catboost_keeps_raw_values(self, mock_config):
        model = RentCostModel({**mock_config, "model_type": "catboost"})
        X = model.preprocess_features(self._df(), ['brand', 'power', 'km'], fit=True)
        assert model.label_encoders == {}
        assert X[0, 0] == 'A'
        assert pd.isna(X[1, 1])


class TestSplit:

    def test_split_shapes_and_columns(self, mock_config, rent_data):
        features, target = rent_data
        model = RentCostModel(mock_config)
        X_tr, X_te, y_tr, y_te = model.prepare_train_test_split(features, target, 0.3, 42)

        assert len(X_tr) + len(X_te) == len(features)
        assert len(y_tr) == len(X_tr) and len(y_te) == len(X_te)
        for col in ('vehicle_id', 'model'):
            assert col not in X_tr.columns
        assert 'brand' in X_tr.columns
        assert len(model._groups_train) == len(X_tr)

    def test_no_brand_model_overlap(self, mock_config, rent_data):
        features, target = rent_data
        model = RentCostModel(mock_config)
        X_tr, X_te, _, _ = model.prepare_train_test_split(features, target, 0.3, 42)

        g = RentCostModel._build_group_key(features, GROUP_COLS)
        assert set(g.loc[X_tr.index]) & set(g.loc[X_te.index]) == set()

    def test_deterministic_with_seed(self, mock_config, rent_data):
        features, target = rent_data
        a = RentCostModel(mock_config).prepare_train_test_split(features, target, 0.3, 7)
        b = RentCostModel(mock_config).prepare_train_test_split(features, target, 0.3, 7)
        assert list(a[0].index) == list(b[0].index)

    def test_custom_group_cols_from_config(self, mock_config, rent_data):
        features, target = rent_data
        model = RentCostModel({**mock_config, "group_cols": ["segment", "brand"]})
        model.prepare_train_test_split(features, target, 0.3, 42)
        assert len(model._groups_train) > 0

    def test_not_enough_groups_raises(self, mock_config):
        features = pd.DataFrame({'vehicle_id': list('abcd'), 'brand': ['A'] * 4,
                                 'model': ['x', 'x', 'y', 'y'], 'km': [1, 2, 3, 4]})
        target = pd.DataFrame({'vehicle_id': list('abcd'), 'target': [1, 2, 3, 4]})
        with pytest.raises(ValueError, match="Pas assez de groupes"):
            RentCostModel(mock_config).prepare_train_test_split(features, target)

    def test_missing_group_column_raises(self, mock_config, rent_data):
        features, target = rent_data
        with pytest.raises(ValueError, match="regroupement"):
            RentCostModel(mock_config).prepare_train_test_split(
                features.drop(columns=['model']), target)

    def test_label_columns_never_features(self, mock_config, rent_data):
        features, target = rent_data
        X_tr, _, _, _ = RentCostModel(mock_config).prepare_train_test_split(features, target)
        assert not any(c.startswith('label_') for c in X_tr.columns)


class TestModelFit:

    def _train_part(self, mock_config, rent_data, cfg=None):
        features, target = rent_data
        model = RentCostModel(cfg or mock_config)
        X_tr, _, y_tr, _ = model.prepare_train_test_split(features, target)
        return model, X_tr, y_tr

    @patch(f'{MODULE}.cross_validate')
    def test_default_uses_cross_validate_with_groups(self, mock_cv, mock_config, rent_data):
        mock_cv.return_value = {
            "test_rmse": np.array([-10.0, -12.0]),
            "test_mae": np.array([-8.0, -9.0]),
            "test_r2": np.array([0.8, 0.82]),
        }
        model, X_tr, y_tr = self._train_part(mock_config, rent_data)

        metrics = model.model_fit(X_tr, y_tr)

        mock_cv.assert_called_once()
        assert 'groups' in mock_cv.call_args.kwargs
        assert metrics['cv_rmse_mean'] == pytest.approx(11.0)
        assert metrics['cv_mae_mean'] == pytest.approx(8.5)
        assert model.model is not None
        assert model.metrics == metrics

    def test_default_real_cv(self, mock_config, rent_data):
        model, X_tr, y_tr = self._train_part(mock_config, rent_data)
        metrics = model.model_fit(X_tr, y_tr)
        assert set(metrics) == {"cv_rmse_mean", "cv_rmse_std", "cv_mae_mean",
                                "cv_mae_std", "cv_r2_mean", "cv_r2_std"}
        assert model.feature_names == X_tr.columns.tolist()

    def test_blend_uses_manual_group_kfold(self, blend_config, rent_data):
        model, X_tr, y_tr = self._train_part(blend_config, rent_data)
        with patch(f'{MODULE}.cross_validate') as mock_cv:
            metrics = model.model_fit(X_tr, y_tr)
        mock_cv.assert_not_called()
        assert isinstance(model.model, BlendRegressor)
        assert 'cv_r2_mean' in metrics

    def test_catboost_style_manual_loop(self, mock_config, rent_data):
        cfg = {**mock_config, "model_type": "catboost"}
        model, X_tr, y_tr = self._train_part(mock_config, rent_data, cfg)
        model._get_model = MagicMock(side_effect=lambda params=None: FakeRegressor())
        with patch(f'{MODULE}.cross_validate') as mock_cv:
            metrics = model.model_fit(X_tr, y_tr)
        mock_cv.assert_not_called()
        assert model._get_model.call_count == 6      # 5 folds + fit final
        assert 'cv_mae_mean' in metrics

    def test_target_transform_trains_on_transformed_target(self, mock_config, rent_data):
        cfg = {**mock_config, "target_transform": "log"}
        model, X_tr, y_tr = self._train_part(mock_config, rent_data, cfg)
        model._get_model = MagicMock(side_effect=lambda params=None: FakeRegressor())

        model.model_fit(X_tr, y_tr)

        # le modèle final apprend log1p(y) -> sa moyenne est celle du log
        assert model.model.mean_ == pytest.approx(np.log1p(y_tr.values).mean())

    def test_explicit_params_take_priority_over_best_params(self, mock_config, rent_data):
        model, X_tr, y_tr = self._train_part(mock_config, rent_data)
        model.best_params = {"max_iter": 5}
        model._get_model = MagicMock(side_effect=lambda params=None: FakeRegressor())
        cfg_model = model
        cfg_model.target_transform = 'log'  # force la boucle manuelle
        model.model_fit(X_tr, y_tr, model_params={"max_iter": 9})
        assert all(c.kwargs['params'] == {"max_iter": 9} for c in model._get_model.call_args_list)


class TestOptuna:

    def test_blend_not_supported(self, blend_config, rent_data):
        features, target = rent_data
        model = RentCostModel(blend_config)
        X_tr, _, y_tr, _ = model.prepare_train_test_split(features, target)
        with pytest.raises(ValueError, match="blend"):
            model.optimize_hyperparams(X_tr, y_tr, n_trials=1)

    def test_optimize_hyperparams_hgb(self, mock_config, rent_data):
        features, target = rent_data
        model = RentCostModel(mock_config)
        X_tr, _, y_tr, _ = model.prepare_train_test_split(features, target)

        best = model.optimize_hyperparams(X_tr, y_tr, n_trials=2)

        assert best['random_state'] == 42 and best['verbose'] == 0
        assert model.results['optuna']['n_trials'] == 2

    @pytest.mark.parametrize("mtype, key", [
        ("hist_gradient_boosting", "max_iter"),
        ("lightgbm", "n_estimators"),
        ("xgboost", "n_estimators"),
        ("catboost", "iterations"),
    ])
    def test_search_space_per_model_type(self, mock_config, mtype, key):
        trial = MagicMock()
        trial.suggest_int.side_effect = lambda n, lo, hi, **k: lo
        trial.suggest_float.side_effect = lambda n, lo, hi, **k: lo
        params = RentCostModel({**mock_config, "model_type": mtype})._get_optuna_params(trial)
        assert key in params


class TestEvaluate:

    def test_evaluate_metrics_keys_and_values(self, mock_config):
        model = RentCostModel(mock_config)
        model.feature_names = ['km']
        model.model = MagicMock()
        model.model.predict.side_effect = lambda X: np.full(len(X), 100.0)
        X = pd.DataFrame({'km': [1.0, 2.0, 3.0]})
        y = pd.Series([100.0, 100.0, 100.0])
        model.preprocess_features(X, ['km'], fit=True)

        m = model.evaluate(X, y, X, y)

        assert set(m) == {"train_mae", "test_mae", "train_rmse", "test_rmse", "train_r2", "test_r2"}
        assert m['test_mae'] == 0.0

    def test_evaluate_inverts_target_transform(self, mock_config):
        model = RentCostModel({**mock_config, "target_transform": "log"})
        model.feature_names = ['km']
        model.model = MagicMock()
        model.model.predict.side_effect = lambda X: np.full(len(X), np.log1p(100.0))
        X = pd.DataFrame({'km': [1.0, 2.0]})
        y = pd.Series([100.0, 100.0])
        model.preprocess_features(X, ['km'], fit=True)

        m = model.evaluate(X, y, X, y)

        assert m['test_mae'] == pytest.approx(0.0, abs=1e-6)


class TestFeatureImportance:

    def test_raises_when_not_trained(self, mock_config):
        with pytest.raises(ValueError):
            RentCostModel(mock_config).get_feature_importance()

    def test_sklearn_sorted_desc(self, mock_config):
        model = RentCostModel(mock_config)
        model.model = MagicMock()
        model.model.feature_importances_ = np.array([0.2, 0.5, 0.3])
        model.feature_names = ['a', 'b', 'c']
        imp = model.get_feature_importance()
        assert list(imp['feature']) == ['b', 'c', 'a']

    def test_catboost(self, mock_config):
        model = RentCostModel({**mock_config, "model_type": "catboost"})
        model.model = MagicMock(spec=['get_feature_importance'])
        model.model.get_feature_importance.return_value = np.array([0.6, 0.4])
        model.feature_names = ['a', 'b']
        assert len(model.get_feature_importance()) == 2

    def test_blend(self, blend_config, rent_data):
        features, target = rent_data
        model = RentCostModel(blend_config)
        X_tr, _, y_tr, _ = model.prepare_train_test_split(features, target)
        model.model_fit(X_tr, y_tr)
        imp = model.get_feature_importance()
        assert len(imp) == X_tr.shape[1]
        assert imp['importance'].sum() == pytest.approx(1.0)

    def test_empty_when_unsupported(self, mock_config):
        model = RentCostModel(mock_config)
        model.model = MagicMock(spec=['predict'])
        model.feature_names = ['a']
        assert model.get_feature_importance().empty


class TestRepeatedSplitEvaluation:

    def test_returns_stats_and_keeps_model_untouched(self, mock_config, rent_data):
        features, target = rent_data
        model = RentCostModel(mock_config)

        res = model.repeated_split_evaluation(features, target, n_repeats=3)

        assert set(res) == {"n_repeats", "r2_mean", "r2_std", "r2_min", "r2_max", "mae_mean"}
        assert res['n_repeats'] == 3
        assert res['r2_min'] <= res['r2_mean'] <= res['r2_max']
        assert model.model is None

    def test_uses_group_cols_and_excludes_labels(self, mock_config, rent_data):
        features, target = rent_data
        model = RentCostModel(mock_config)
        seen = {}
        orig = RentCostModel.preprocess_features

        def spy(self, df, feature_list, fit=True):
            seen.setdefault('cols', list(feature_list))
            return orig(self, df, feature_list, fit)

        with patch.object(RentCostModel, 'preprocess_features', spy):
            model.repeated_split_evaluation(features, target, n_repeats=1)

        assert 'model' not in seen['cols'] and 'vehicle_id' not in seen['cols']
        assert not any(c.startswith('label_') for c in seen['cols'])


class TestTrainModelOrchestrator:

    def _run(self, config, rent_data):
        features, target = rent_data
        model = RentCostModel(config)
        with patch.object(RentCostModel, 'generate_evaluation_figures') as figs:
            results = model.train_model(features, target)
        return model, results, figs

    def test_end_to_end(self, mock_config, rent_data):
        model, results, figs = self._run(mock_config, rent_data)

        assert 'train_metrics' in results and 'test_metrics' in results
        assert 'repeated_split_eval' not in results
        assert 'shap_importance' not in results
        figs.assert_called_once()
        assert 'vehicle_id' not in model.X_test.columns
        assert 'model' not in model.X_test.columns
        assert not any(c.startswith('label_') for c in model.feature_names)

    def test_exclude_features_not_used(self, mock_config, rent_data):
        model, _, _ = self._run({**mock_config, "exclude_features": ["segment"]}, rent_data)
        assert 'segment' not in model.feature_names

    def test_eval_repeats_enabled(self, mock_config, rent_data):
        _, results, _ = self._run({**mock_config, "eval_repeats": 2}, rent_data)
        assert results['repeated_split_eval']['n_repeats'] == 2

    def test_optuna_branch(self, mock_config, rent_data):
        features, target = rent_data
        model = RentCostModel({**mock_config, "use_optuna": True, "optuna_n_trials": 3})
        with patch.object(RentCostModel, 'optimize_hyperparams',
                          return_value={"max_iter": 10, "random_state": 42}) as opt, \
                patch.object(RentCostModel, 'generate_evaluation_figures'):
            model.train_model(features, target)
        opt.assert_called_once()
        assert opt.call_args.kwargs['n_trials'] == 3

    def test_shap_branch_called_when_enabled(self, mock_config, rent_data):
        features, target = rent_data
        model = RentCostModel({**mock_config, "use_shap": True})
        with patch.object(RentCostModel, 'generate_evaluation_figures'), \
                patch.object(RentCostModel, 'generate_shap_analysis') as shap_mock:
            model.train_model(features, target)
        shap_mock.assert_called_once()

    def test_blend_end_to_end(self, blend_config, rent_data):
        model, results, _ = self._run(blend_config, rent_data)
        assert isinstance(model.model, BlendRegressor)
        assert 'test_r2' in results['test_metrics']
        assert len(results['feature_importance']) == len(model.feature_names)


class TestSaveModel:

    def _prep(self, config):
        model = RentCostModel(config)
        model.feature_names = ['year', 'mileage']
        model.categorical_features = []
        model.numeric_features = ['year', 'mileage']
        model.metrics = {'cv_rmse_mean': 10.5, 'cv_r2_mean': float('nan')}
        model.scaler.fit(np.array([[2020., 10000.], [2019., 20000.]]))
        model.model = MagicMock()
        return model

    @patch(f'{MODULE}.onnx.save_model')
    @patch(f'{MODULE}.convert_sklearn')
    def test_default_onnx_and_metadata(self, mock_convert, mock_save, mock_config):
        model = self._prep(mock_config)
        path = model.save_model({'train_metrics': {}}, mock_config)

        mock_convert.assert_called_once()
        mock_save.assert_called_once()
        meta = json.loads((path / "metadata.json").read_text())
        assert meta['format'] == 'onnx'
        assert meta['target_transform'] == 'none'
        assert meta['blend_members'] is None
        assert meta['metrics']['cv_r2_mean'] is None     # NaN nettoyé
        for f in ("scaler.json", "training_results.json", "config.yaml"):
            assert (path / f).exists()

    @patch(f'{MODULE}.onnx.save_model')
    @patch(f'{MODULE}.convert_sklearn')
    def test_label_encoders_and_optuna_files(self, mock_convert, mock_save, mock_config):
        from sklearn.preprocessing import OrdinalEncoder
        model = self._prep(mock_config)
        enc = OrdinalEncoder().fit(pd.DataFrame({'brand': ['A', 'B']}))
        model.label_encoders = {'brand': enc}
        model.best_params = {"max_iter": 10}

        path = model.save_model({}, mock_config)

        assert json.loads((path / "label_encoders.json").read_text())['brand']['classes'] == ['A', 'B']
        assert (path / "optuna_best_params.json").exists()

    def test_catboost_native_format(self, mock_config):
        cfg = {**mock_config, "model_type": "catboost"}
        model = self._prep(cfg)
        with patch(f'{MODULE}.convert_sklearn') as conv, patch(f'{MODULE}.onnx.save_model') as sv:
            path = model.save_model({}, cfg)
        model.model.save_model.assert_called_once()
        assert model.model.save_model.call_args.kwargs['format'] == 'cbm'
        conv.assert_not_called() and sv.assert_not_called()
        assert not (path / "scaler.json").exists()
        assert json.loads((path / "metadata.json").read_text())['format'] == 'cbm'

    @patch(f'{MODULE}.onnx.save_model')
    @patch(f'{MODULE}.convert_sklearn')
    def test_blend_exports_each_member(self, mock_convert, mock_save, blend_config):
        model = self._prep(blend_config)
        model.model = BlendRegressor([("hist_gradient_boosting", FakeRegressor()),
                                      ("extra_trees", FakeRegressor())])

        path = model.save_model({}, blend_config)

        assert mock_convert.call_count == 2
        assert mock_save.call_count == 2
        meta = json.loads((path / "metadata.json").read_text())
        assert meta['format'] == 'onnx_blend'
        assert [m['file'] for m in meta['blend_members']] == [
            "model_hist_gradient_boosting.onnx", "model_extra_trees.onnx"]

    @patch(f'{MODULE}.onnx.save_model')
    def test_blend_lightgbm_uses_onnxmltools(self, mock_save, blend_config):
        model = self._prep(blend_config)
        model.model = BlendRegressor([("lightgbm", FakeRegressor())])
        fake_tools = MagicMock()
        with patch.dict(sys.modules, {'onnxmltools': fake_tools}):
            model.save_model({}, blend_config)
        fake_tools.convert_lightgbm.assert_called_once()

    @patch(f'{MODULE}.convert_sklearn', side_effect=Exception("boom"))
    def test_export_failure_wrapped(self, mock_convert, mock_config):
        model = self._prep(mock_config)
        with pytest.raises(RuntimeError, match="Model export failed"):
            model.save_model({}, mock_config)


class TestShapAndFigures:

    def _trained(self, config, rent_data):
        features, target = rent_data
        model = RentCostModel(config)
        X_tr, X_te, y_tr, y_te = model.prepare_train_test_split(features, target)
        model.model_fit(X_tr, y_tr)
        return model, X_te, y_te

    def test_figures_four_files_without_feature_importance(self, mock_config, rent_data):
        # HistGradientBoosting n'expose pas feature_importances_ -> pas de figure 5
        model, X_te, y_te = self._trained(mock_config, rent_data)
        with patch('matplotlib.pyplot.savefig') as sv:
            model.generate_evaluation_figures(X_te, y_te)
        assert sv.call_count == 4

    def test_figures_five_files_with_blend_importance(self, blend_config, rent_data):
        model, X_te, y_te = self._trained(blend_config, rent_data)
        with patch('matplotlib.pyplot.savefig') as sv:
            model.generate_evaluation_figures(X_te, y_te)
        assert sv.call_count == 5

    def test_generate_shap_analysis_hgb(self, mock_config, rent_data):
        model, X_te, y_te = self._trained(mock_config, rent_data)
        with patch('matplotlib.pyplot.savefig') as sv:
            model.generate_shap_analysis(X_te, y_te)
        assert sv.call_count == 3
        assert len(model.results['shap_importance']) == len(model.feature_names)

    def test_generate_shap_analysis_blend_uses_member(self, blend_config, rent_data):
        model, X_te, y_te = self._trained(blend_config, rent_data)
        with patch('matplotlib.pyplot.savefig'), \
                patch(f'{MODULE}.shap.TreeExplainer') as expl:
            expl.return_value.return_value = MagicMock(values=np.ones((len(X_te), len(model.feature_names))))
            with patch(f'{MODULE}.shap.summary_plot'):
                model.generate_shap_analysis(X_te, y_te)
        expl.assert_called_once_with(model.model.shap_member())

    def test_shap_falls_back_to_kernel_explainer(self, mock_config, rent_data):
        model, X_te, y_te = self._trained(mock_config, rent_data)
        with patch('matplotlib.pyplot.savefig'), \
                patch(f'{MODULE}.shap.TreeExplainer', side_effect=Exception("nope")), \
                patch(f'{MODULE}.shap.kmeans'), \
                patch(f'{MODULE}.shap.summary_plot'), \
                patch(f'{MODULE}.shap.KernelExplainer') as kern:
            kern.return_value.shap_values.return_value = np.ones((len(X_te), len(model.feature_names)))
            model.generate_shap_analysis(X_te, y_te)
        kern.assert_called_once()


class TestCleanup:

    @patch('shutil.rmtree')
    def test_remove_model_folder(self, mock_rmtree, mock_config):
        RentCostModel(mock_config).remove_model_folder_from_local()
        mock_rmtree.assert_called_once()

    @patch('shutil.rmtree', side_effect=OSError("denied"))
    def test_remove_model_folder_swallows_errors(self, mock_rmtree, mock_config):
        RentCostModel(mock_config).remove_model_folder_from_local()