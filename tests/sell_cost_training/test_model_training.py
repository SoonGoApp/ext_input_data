"""
Tests unitaires pour model_training.py - Sell Cost (Rebate Price)
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, mock_open
from soongo_data.utils.sell_cost_training.model_training import SellCostModel


@pytest.fixture
def mock_config():
    return {
        "model_type": "hist_gradient_boosting",
        "test_size": 0.3,
        "random_state": 42,
        "models_dir": "/tmp/models",
        "bucket_name": "test-bucket",
        "use_optuna": False,
        "use_shap": False,
        "model_params": {
            "max_iter": 100,
            "random_state": 42
        }
    }


@pytest.fixture
def sample_features():
    """Chaque ligne a une signature unique -> 5 groupes distincts."""
    return pd.DataFrame({
        'vehicle_id': ['v1', 'v2', 'v3', 'v4', 'v5'],
        'brand':      ['Toyota', 'Ford', 'Honda', 'Toyota', 'Ford'],
        'entry_year': [2020, 2019, 2021, 2020, 2018],
        'age':        [6, 7, 5, 6, 8],
        'segment':    ['SUV', 'Berline', 'SUV', 'Berline', 'SUV'],
        'energy':     ['Diesel', 'Petrol', 'Electric', 'Diesel', 'Petrol'],
        'fiscal_power': [6.0, 7.0, 5.0, 6.0, 8.0],
        'seat_count':   [5.0, 5.0, 5.0, 7.0, 5.0],
        'transmission': ['Manual', 'Auto', 'Auto', 'Manual', 'Auto'],
        'motor_power':  [110.0, 130.0, 150.0, 110.0, 90.0],
    })


@pytest.fixture
def sample_target():
    return pd.DataFrame({
        'vehicle_id': ['v1', 'v2', 'v3', 'v4', 'v5'],
        'target':     [25000, 32000, 28000, 26000, 30000]
    })


class FakeRegressor:
    """Modèle factice pour tester la boucle CatBoost sans dépendre d'un vrai fit."""

    def __init__(self, *args, **kwargs):
        self.fitted = False

    def fit(self, X, y, *args, **kwargs):
        self.fitted = True
        return self

    def predict(self, X):
        return np.full(len(X), 28000.0)


class TestSellCostModel:
    """Tests pour SellCostModel"""

    # ------------------------------------------------------------------
    # INIT / MODEL FACTORY
    # ------------------------------------------------------------------

    def test_init(self, mock_config):
        model = SellCostModel(mock_config)

        assert model.model_type == "hist_gradient_boosting"
        assert model.test_size == 0.3
        assert model.random_state == 42
        assert model.model is None
        assert model.feature_importance == {}
        assert model.best_params is None

    def test_get_model_default(self, mock_config):
        model = SellCostModel(mock_config)

        base_model = model._get_model()

        assert base_model is not None
        assert hasattr(base_model, 'fit')

    def test_get_model_catboost(self, mock_config):
        pytest.importorskip("catboost")

        config = {**mock_config, "model_type": "catboost"}
        model = SellCostModel(config)
        model.feature_names = ['brand', 'motor_power']
        model.categorical_features = ['brand']

        base_model = model._get_model(params={"iterations": 10, "verbose": 0})

        assert base_model.__class__.__name__ == "CatBoostRegressor"

    # ------------------------------------------------------------------
    # PREPROCESSING
    # ------------------------------------------------------------------

    def test_preprocess_features_fit(self, mock_config, sample_features):
        model = SellCostModel(mock_config)
        feature_list = ['brand', 'entry_year', 'age', 'energy', 'fiscal_power',
                         'seat_count', 'transmission', 'motor_power', 'segment']

        X = model.preprocess_features(sample_features, feature_list, fit=True)

        assert X.shape[0] == 5
        assert X.shape[1] == len(feature_list)
        assert 'brand' in model.categorical_features
        assert 'energy' in model.categorical_features
        assert 'transmission' in model.categorical_features
        assert 'segment' in model.categorical_features
        assert 'entry_year' in model.numeric_features
        assert 'age' in model.numeric_features

    def test_preprocess_features_transform(self, mock_config, sample_features):
        model = SellCostModel(mock_config)
        feature_list = ['brand', 'entry_year', 'age', 'energy', 'fiscal_power',
                         'seat_count', 'transmission', 'motor_power', 'segment']

        model.preprocess_features(sample_features, feature_list, fit=True)
        X = model.preprocess_features(sample_features, feature_list, fit=False)

        assert X.shape[0] == 5
        assert X.shape[1] == len(feature_list)

    # ------------------------------------------------------------------
    # GROUP KEY BUILDER
    # ------------------------------------------------------------------

    def test_build_group_key_basic(self, mock_config):
        df = pd.DataFrame({
            'brand': ['Toyota', 'Ford'],
            'segment': ['SUV', 'Berline'],
        })

        groups = SellCostModel._build_group_key(df, ['brand', 'segment'])

        assert list(groups) == ['Toyota|SUV', 'Ford|Berline']

    def test_build_group_key_fills_nan_with_unknown(self, mock_config):
        df = pd.DataFrame({
            'brand': ['Toyota', None],
            'segment': ['SUV', 'Berline'],
        })

        groups = SellCostModel._build_group_key(df, ['brand', 'segment'])

        assert groups.iloc[1] == 'unknown|Berline'

    def test_build_group_key_ignores_missing_columns(self, mock_config):
        df = pd.DataFrame({'brand': ['Toyota', 'Ford']})

        groups = SellCostModel._build_group_key(df, ['brand', 'not_a_column'])

        assert list(groups) == ['Toyota', 'Ford']

    def test_build_group_key_duplicate_rows_share_group(self, mock_config):
        df = pd.DataFrame({
            'brand': ['Toyota', 'Toyota', 'Ford'],
            'segment': ['SUV', 'SUV', 'Berline'],
        })

        groups = SellCostModel._build_group_key(df, ['brand', 'segment'])

        assert groups.nunique() == 2
        assert groups.iloc[0] == groups.iloc[1]

    # ------------------------------------------------------------------
    # DATA CLEANING (seuil target >= 1000 côté sell)
    # ------------------------------------------------------------------

    def test_clean_training_data_drops_duplicate_vehicle_id(self, mock_config):
        df = pd.DataFrame({
            'vehicle_id': ['v1', 'v1', 'v2'],
            'segment': ['SUV', 'SUV', 'Berline'],
            'target': [25000, 25000, 28000],
        })

        cleaned = SellCostModel.clean_training_data(df)

        assert len(cleaned) == 2
        assert cleaned['vehicle_id'].nunique() == 2

    def test_clean_training_data_filters_bad_segments(self, mock_config):
        df = pd.DataFrame({
            'vehicle_id': ['v1', 'v2', 'v3'],
            'segment': ['SUV', 'SCOOTER', 'unknown'],
            'target': [25000, 28000, 30000],
        })

        cleaned = SellCostModel.clean_training_data(df)

        assert list(cleaned['segment']) == ['SUV']

    def test_clean_training_data_filters_target_below_1000(self, mock_config):
        df = pd.DataFrame({
            'vehicle_id': ['v1', 'v2'],
            'segment': ['SUV', 'SUV'],
            'target': [25000, 500],
        })

        cleaned = SellCostModel.clean_training_data(df)

        assert list(cleaned['target']) == [25000]

    # ------------------------------------------------------------------
    # TRAIN / TEST SPLIT (group-aware)
    # ------------------------------------------------------------------

    def test_prepare_train_test_split(self, mock_config, sample_features, sample_target):
        model = SellCostModel(mock_config)

        X_train, X_test, y_train, y_test = model.prepare_train_test_split(
            sample_features, sample_target, test_size=0.3, random_state=42
        )

        assert len(X_train) + len(X_test) == 5
        assert len(y_train) + len(y_test) == 5
        assert 'vehicle_id' not in X_train.columns
        assert hasattr(model, '_groups_train')
        assert len(model._groups_train) == len(X_train)

    def test_prepare_train_test_split_no_group_overlap(self, mock_config, sample_features, sample_target):
        model = SellCostModel(mock_config)

        X_train, X_test, y_train, y_test = model.prepare_train_test_split(
            sample_features, sample_target, test_size=0.3, random_state=42
        )

        feature_cols = [c for c in sample_features.columns if c != 'vehicle_id']
        groups_train = model._build_group_key(X_train, feature_cols)
        groups_test = model._build_group_key(X_test, feature_cols)

        assert set(groups_train) & set(groups_test) == set()

    # ------------------------------------------------------------------
    # MODEL FIT (group-aware CV)
    # ------------------------------------------------------------------

    @patch('soongo_data.utils.sell_cost_training.model_training.cross_validate')
    def test_model_fit_default_model(self, mock_cross_validate, mock_config):
        model = SellCostModel(mock_config)

        mock_cross_validate.return_value = {
            "test_rmse": np.array([-1500.0, -1600.0, -1550.0]),
            "test_mae": np.array([-1000.0, -1100.0, -1050.0]),
            "test_r2": np.array([0.80, 0.82, 0.79]),
        }

        X_train = pd.DataFrame({
            'brand':        ['Toyota', 'Ford', 'Honda'],
            'entry_year':   [2020, 2019, 2021],
            'age':          [6, 7, 5],
            'fiscal_power': [6.0, 7.0, 5.0],
            'motor_power':  [110.0, 130.0, 150.0],
        })
        y_train = pd.Series([25000, 32000, 28000])
        model._groups_train = pd.Series(['g1', 'g2', 'g3'])

        metrics = model.model_fit(X_train, y_train)

        assert 'cv_rmse_mean' in metrics
        assert 'cv_mae_mean' in metrics
        assert 'cv_r2_mean' in metrics
        assert metrics['cv_rmse_mean'] == pytest.approx(1550.0)
        assert model.model is not None
        mock_cross_validate.assert_called_once()
        assert 'groups' in mock_cross_validate.call_args.kwargs

    def test_model_fit_catboost_manual_group_kfold(self, mock_config):
        config = {**mock_config, "model_type": "catboost"}
        model = SellCostModel(config)
        model._get_model = MagicMock(side_effect=lambda params=None: FakeRegressor())

        X_train = pd.DataFrame({
            'brand': ['A', 'B', 'C', 'D', 'E', 'F'],
            'motor_power': [100, 110, 120, 130, 140, 150],
        })
        y_train = pd.Series([25000, 26000, 27000, 28000, 29000, 30000])
        model._groups_train = pd.Series(['g1', 'g2', 'g3', 'g4', 'g5', 'g6'])

        metrics = model.model_fit(X_train, y_train)

        assert 'cv_rmse_mean' in metrics
        assert 'cv_mae_mean' in metrics
        assert 'cv_r2_mean' in metrics
        assert model.model is not None
        assert model._get_model.call_count >= 5

    # ------------------------------------------------------------------
    # EVALUATE
    # ------------------------------------------------------------------

    def test_evaluate(self, mock_config):
        model = SellCostModel(mock_config)

        model.feature_names = ['entry_year', 'age', 'fiscal_power', 'motor_power']
        model.numeric_features = ['entry_year', 'age', 'fiscal_power', 'motor_power']
        model.categorical_features = []
        model.label_encoders = {}
        model.model = MagicMock()
        model.model.predict.return_value = np.array([25000, 32000, 28000])
        model.scaler = MagicMock()
        model.scaler.transform.return_value = np.array([
            [2020, 6, 6.0, 110.0],
            [2019, 7, 7.0, 130.0],
            [2021, 5, 5.0, 150.0]
        ])

        X = pd.DataFrame({
            'entry_year':   [2020, 2019, 2021],
            'age':          [6, 7, 5],
            'fiscal_power': [6.0, 7.0, 5.0],
            'motor_power':  [110.0, 130.0, 150.0],
        })
        y = pd.Series([25000, 32000, 28000])

        metrics = model.evaluate(X, y, X, y)

        assert 'train_mae' in metrics
        assert 'test_mae' in metrics
        assert 'train_r2' in metrics
        assert 'test_r2' in metrics
        assert 'train_rmse' in metrics
        assert 'test_rmse' in metrics

    # ------------------------------------------------------------------
    # FEATURE IMPORTANCE
    # ------------------------------------------------------------------

    def test_get_feature_importance_raises_when_not_trained(self, mock_config):
        model = SellCostModel(mock_config)

        with pytest.raises(ValueError):
            model.get_feature_importance()

    def test_get_feature_importance_sklearn(self, mock_config):
        model = SellCostModel(mock_config)

        model.model = MagicMock()
        model.model.feature_importances_ = np.array([0.4, 0.3, 0.15, 0.1, 0.05])
        model.feature_names = ['entry_year', 'age', 'brand', 'fiscal_power', 'motor_power']

        importance = model.get_feature_importance()

        assert len(importance) == 5
        assert 'feature' in importance.columns
        assert 'importance' in importance.columns
        assert importance.iloc[0]['importance'] >= importance.iloc[1]['importance']

    def test_get_feature_importance_catboost(self, mock_config):
        config = {**mock_config, "model_type": "catboost"}
        model = SellCostModel(config)

        model.model = MagicMock(spec=['get_feature_importance'])
        model.model.get_feature_importance.return_value = np.array([0.6, 0.4])
        model.feature_names = ['brand', 'motor_power']

        importance = model.get_feature_importance()

        assert len(importance) == 2
        model.model.get_feature_importance.assert_called_once()

    # ------------------------------------------------------------------
    # SAVE MODEL
    # ------------------------------------------------------------------

    @patch('soongo_data.utils.sell_cost_training.model_training.onnx.save_model')
    @patch('soongo_data.utils.sell_cost_training.model_training.convert_sklearn')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.mkdir')
    def test_save_model_default(self, mock_mkdir, mock_file, mock_convert, mock_save, mock_config):
        model = SellCostModel(mock_config)
        model.model = MagicMock()
        model.feature_names = ['entry_year', 'age', 'fiscal_power', 'motor_power']
        model.categorical_features = []
        model.numeric_features = ['entry_year', 'age', 'fiscal_power', 'motor_power']
        model.metrics = {'cv_rmse_mean': 1500.0}
        model.scaler = MagicMock()
        model.scaler.mean_ = np.array([2020, 6, 6.0, 110.0])
        model.scaler.scale_ = np.array([2.0, 1.5, 1.0, 20.0])
        model.scaler.var_ = np.array([4.0, 2.25, 1.0, 400.0])
        model.scaler.with_mean = True
        model.scaler.with_std = True
        model.scaler.n_features_in_ = 4
        model.label_encoders = {}

        mock_convert.return_value = MagicMock()

        model_path = model.save_model({'train_metrics': {}}, mock_config)

        assert model_path is not None
        mock_convert.assert_called_once()
        mock_save.assert_called_once()

    @patch('soongo_data.utils.sell_cost_training.model_training.onnx.save_model')
    @patch('soongo_data.utils.sell_cost_training.model_training.convert_sklearn')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.mkdir')
    def test_save_model_catboost(self, mock_mkdir, mock_file, mock_convert, mock_save, mock_config):
        config = {**mock_config, "model_type": "catboost"}
        model = SellCostModel(config)
        model.model = MagicMock()
        model.feature_names = ['brand', 'motor_power']
        model.categorical_features = ['brand']
        model.numeric_features = ['motor_power']
        model.metrics = {'cv_rmse_mean': 1200.0}
        model.label_encoders = {}
        model.best_params = None

        model_path = model.save_model({'train_metrics': {}}, config)

        assert model_path is not None
        model.model.save_model.assert_called_once()
        call_args = model.model.save_model.call_args
        assert call_args.kwargs.get('format') == 'cbm'
        mock_convert.assert_not_called()
        mock_save.assert_not_called()

    # ------------------------------------------------------------------
    # CLEANUP / FIGURES
    # ------------------------------------------------------------------

    @patch('shutil.rmtree')
    def test_remove_model_folder(self, mock_rmtree, mock_config):
        model = SellCostModel(mock_config)

        model.remove_model_folder_from_local()

        mock_rmtree.assert_called_once()

    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    @patch('pathlib.Path.mkdir')
    def test_generate_evaluation_figures(self, mock_mkdir, mock_close, mock_savefig, mock_config):
        model = SellCostModel(mock_config)
        model.model = MagicMock()
        model.model.predict.return_value = np.array([25000, 32000, 28000])
        model.feature_names = ['entry_year', 'age', 'fiscal_power', 'motor_power']
        model.numeric_features = ['entry_year', 'age', 'fiscal_power', 'motor_power']
        model.categorical_features = []
        model.label_encoders = {}
        model.scaler = MagicMock()
        model.scaler.transform.return_value = np.array([
            [2020, 6, 6.0, 110.0],
            [2019, 7, 7.0, 130.0],
            [2021, 5, 5.0, 150.0]
        ])
        model.get_feature_importance = MagicMock(return_value=pd.DataFrame())

        X_test = pd.DataFrame({
            'entry_year':   [2020, 2019, 2021],
            'age':          [6, 7, 5],
            'fiscal_power': [6.0, 7.0, 5.0],
            'motor_power':  [110.0, 130.0, 150.0],
        })
        y_test = pd.Series([25000, 32000, 28000])

        model.generate_evaluation_figures(X_test, y_test)

        assert mock_savefig.call_count >= 4