"""
Tests unitaires pour model_training.py
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from soongo_data.utils.rent_cost_training.model_training import RentCostModel


@pytest.fixture
def mock_config():
    """Configuration de test"""
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
    """DataFrame de features de test - chaque ligne a une signature unique
    (donc 5 groupes distincts via _build_group_key)."""
    return pd.DataFrame({
        'vehicle_id': ['v1', 'v2', 'v3', 'v4', 'v5'],
        'brand': ['Toyota', 'Ford', 'Honda', 'Toyota', 'Ford'],
        'year': [2020, 2019, 2021, 2020, 2018],
        'mileage': [10000, 20000, 5000, 15000, 30000],
        'fuel_type': ['Diesel', 'Petrol', 'Electric', 'Diesel', 'Petrol']
    })


@pytest.fixture
def sample_target():
    """DataFrame de target de test"""
    return pd.DataFrame({
        'vehicle_id': ['v1', 'v2', 'v3', 'v4', 'v5'],
        'target': [500, 600, 550, 520, 580]
    })


class FakeRegressor:
    """Modèle factice utilisé pour tester la boucle CatBoost sans dépendre
    d'un vrai fit CatBoost (rapide, déterministe)."""

    def __init__(self, *args, **kwargs):
        self.fitted = False

    def fit(self, X, y, *args, **kwargs):
        self.fitted = True
        return self

    def predict(self, X):
        return np.full(len(X), 500.0)


class TestRentCostModel:
    """Tests pour RentCostModel"""

    # ------------------------------------------------------------------
    # INIT / MODEL FACTORY
    # ------------------------------------------------------------------

    def test_init(self, mock_config):
        """Test initialisation du modèle"""
        model = RentCostModel(mock_config)

        assert model.model_type == "hist_gradient_boosting"
        assert model.test_size == 0.3
        assert model.random_state == 42
        assert model.model is None
        assert model.best_params is None

    def test_get_model_default(self, mock_config):
        """Test récupération du modèle par défaut (hist_gradient_boosting)"""
        model = RentCostModel(mock_config)

        base_model = model._get_model()

        assert base_model is not None
        assert hasattr(base_model, 'fit')

    def test_get_model_catboost(self, mock_config):
        """Test dispatch vers CatBoost quand model_type == 'catboost'"""
        pytest.importorskip("catboost")

        config = {**mock_config, "model_type": "catboost"}
        model = RentCostModel(config)
        model.feature_names = ['segment', 'motor_power']
        model.categorical_features = ['segment']

        base_model = model._get_model(params={"iterations": 10, "verbose": 0})

        assert base_model.__class__.__name__ == "CatBoostRegressor"

    # ------------------------------------------------------------------
    # PREPROCESSING
    # ------------------------------------------------------------------

    def test_preprocess_features_fit(self, mock_config, sample_features):
        """Test preprocessing avec fit"""
        model = RentCostModel(mock_config)
        feature_list = ['brand', 'year', 'mileage', 'fuel_type']

        X = model.preprocess_features(sample_features, feature_list, fit=True)

        assert X.shape[0] == 5
        assert X.shape[1] == 4
        assert len(model.categorical_features) == 2  # brand, fuel_type
        assert len(model.numeric_features) == 2  # year, mileage

    def test_preprocess_features_transform(self, mock_config, sample_features):
        """Test preprocessing sans fit"""
        model = RentCostModel(mock_config)
        feature_list = ['brand', 'year', 'mileage', 'fuel_type']

        model.preprocess_features(sample_features, feature_list, fit=True)
        X = model.preprocess_features(sample_features, feature_list, fit=False)

        assert X.shape[0] == 5
        assert X.shape[1] == 4

    # ------------------------------------------------------------------
    # GROUP KEY BUILDER (nouveau)
    # ------------------------------------------------------------------

    def test_build_group_key_basic(self, mock_config):
        """Test construction de la clé de groupe à partir de plusieurs colonnes"""
        df = pd.DataFrame({
            'brand': ['Toyota', 'Ford'],
            'segment': ['SUV', 'CITY'],
        })

        groups = RentCostModel._build_group_key(df, ['brand', 'segment'])

        assert list(groups) == ['Toyota|SUV', 'Ford|CITY']

    def test_build_group_key_fills_nan_with_unknown(self, mock_config):
        """Test que les NaN sont remplacés par 'unknown' dans la clé de groupe"""
        df = pd.DataFrame({
            'brand': ['Toyota', None],
            'segment': ['SUV', 'CITY'],
        })

        groups = RentCostModel._build_group_key(df, ['brand', 'segment'])

        assert groups.iloc[1] == 'unknown|CITY'

    def test_build_group_key_ignores_missing_columns(self, mock_config):
        """Test que les colonnes absentes du DataFrame sont ignorées sans lever d'erreur"""
        df = pd.DataFrame({'brand': ['Toyota', 'Ford']})

        groups = RentCostModel._build_group_key(df, ['brand', 'not_a_column'])

        assert list(groups) == ['Toyota', 'Ford']

    def test_build_group_key_duplicate_rows_share_group(self, mock_config):
        """Deux lignes avec exactement les mêmes valeurs de features doivent
        former le même groupe (c'est ce qui évite le data leakage)."""
        df = pd.DataFrame({
            'brand': ['Toyota', 'Toyota', 'Ford'],
            'segment': ['SUV', 'SUV', 'CITY'],
        })

        groups = RentCostModel._build_group_key(df, ['brand', 'segment'])

        assert groups.nunique() == 2
        assert groups.iloc[0] == groups.iloc[1]

    # ------------------------------------------------------------------
    # DATA CLEANING (nouveau)
    # ------------------------------------------------------------------

    def test_clean_training_data_drops_duplicate_vehicle_id(self, mock_config):
        df = pd.DataFrame({
            'vehicle_id': ['v1', 'v1', 'v2'],
            'segment': ['SUV', 'SUV', 'CITY'],
            'target': [100, 100, 200],
        })

        cleaned = RentCostModel.clean_training_data(df)

        assert len(cleaned) == 2
        assert cleaned['vehicle_id'].nunique() == 2

    def test_clean_training_data_filters_bad_segments(self, mock_config):
        df = pd.DataFrame({
            'vehicle_id': ['v1', 'v2', 'v3'],
            'segment': ['SUV', 'SCOOTER', 'unknown'],
            'target': [100, 200, 300],
        })

        cleaned = RentCostModel.clean_training_data(df)

        assert list(cleaned['segment']) == ['SUV']

    def test_clean_training_data_filters_negative_target(self, mock_config):
        df = pd.DataFrame({
            'vehicle_id': ['v1', 'v2'],
            'segment': ['SUV', 'SUV'],
            'target': [100, -50],
        })

        cleaned = RentCostModel.clean_training_data(df)

        assert list(cleaned['target']) == [100]

    # ------------------------------------------------------------------
    # TRAIN / TEST SPLIT (group-aware)
    # ------------------------------------------------------------------

    def test_prepare_train_test_split(self, mock_config, sample_features, sample_target):
        """Test split train/test group-aware"""
        model = RentCostModel(mock_config)

        X_train, X_test, y_train, y_test = model.prepare_train_test_split(
            sample_features, sample_target, test_size=0.3, random_state=42
        )

        assert len(X_train) + len(X_test) == 5
        assert len(y_train) + len(y_test) == 5
        assert 'vehicle_id' not in X_train.columns
        # les groupes du train sont bien conservés pour la CV interne
        assert hasattr(model, '_groups_train')
        assert len(model._groups_train) == len(X_train)

    def test_prepare_train_test_split_no_group_overlap(self, mock_config, sample_features, sample_target):
        """Aucun groupe (signature complète des features) ne doit apparaître
        à la fois en train et en test."""
        model = RentCostModel(mock_config)

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

    @patch('soongo_data.utils.rent_cost_training.model_training.cross_validate')
    def test_model_fit_default_model(self, mock_cross_validate, mock_config):
        """Test entraînement group-aware pour un modèle sklearn-compatible
        (hist_gradient_boosting) - la CV elle-même est mockée."""
        model = RentCostModel(mock_config)

        mock_cross_validate.return_value = {
            "test_rmse": np.array([-10.0, -12.0, -11.0]),
            "test_mae": np.array([-8.0, -9.0, -7.5]),
            "test_r2": np.array([0.80, 0.82, 0.79]),
        }

        X_train = pd.DataFrame({
            'brand': ['Toyota', 'Ford', 'Honda'],
            'year': [2020, 2019, 2021],
            'mileage': [10000, 20000, 5000],
        })
        y_train = pd.Series([500, 600, 550])
        model._groups_train = pd.Series(['g1', 'g2', 'g3'])

        metrics = model.model_fit(X_train, y_train)

        assert 'cv_rmse_mean' in metrics
        assert 'cv_mae_mean' in metrics
        assert 'cv_r2_mean' in metrics
        assert metrics['cv_rmse_mean'] == pytest.approx(11.0)
        assert model.model is not None
        mock_cross_validate.assert_called_once()
        # les groupes doivent être passés à cross_validate
        assert 'groups' in mock_cross_validate.call_args.kwargs

    def test_model_fit_catboost_manual_group_kfold(self, mock_config):
        """Test la boucle manuelle GroupKFold utilisée pour CatBoost
        (cross_validate ne supporte pas CatBoost -> CV faite à la main)."""
        config = {**mock_config, "model_type": "catboost"}
        model = RentCostModel(config)
        model._get_model = MagicMock(side_effect=lambda params=None: FakeRegressor())

        X_train = pd.DataFrame({
            'segment': ['A', 'B', 'C', 'D', 'E', 'F'],
            'motor_power': [100, 110, 120, 130, 140, 150],
        })
        y_train = pd.Series([500, 510, 520, 530, 540, 550])
        # 6 groupes uniques >= n_splits=5 requis par GroupKFold
        model._groups_train = pd.Series(['g1', 'g2', 'g3', 'g4', 'g5', 'g6'])

        metrics = model.model_fit(X_train, y_train)

        assert 'cv_rmse_mean' in metrics
        assert 'cv_mae_mean' in metrics
        assert 'cv_r2_mean' in metrics
        assert model.model is not None
        assert model._get_model.call_count >= 5  # 5 folds + le fit final

    # ------------------------------------------------------------------
    # EVALUATE
    # ------------------------------------------------------------------

    def test_evaluate(self, mock_config):
        """Test évaluation du modèle"""
        model = RentCostModel(mock_config)

        model.feature_names = ['year', 'mileage']
        model.numeric_features = ['year', 'mileage']
        model.categorical_features = []
        model.label_encoders = {}
        model.model = MagicMock()
        model.model.predict.return_value = np.array([500, 600, 550])
        model.scaler = MagicMock()
        model.scaler.transform.return_value = np.array([[2020, 10000], [2019, 20000], [2021, 5000]])

        X = pd.DataFrame({'year': [2020, 2019, 2021], 'mileage': [10000, 20000, 5000]})
        y = pd.Series([500, 600, 550])

        metrics = model.evaluate(X, y, X, y)

        assert 'train_mae' in metrics
        assert 'test_mae' in metrics
        assert 'train_r2' in metrics
        assert 'test_r2' in metrics

    # ------------------------------------------------------------------
    # FEATURE IMPORTANCE
    # ------------------------------------------------------------------

    def test_get_feature_importance_raises_when_not_trained(self, mock_config):
        model = RentCostModel(mock_config)

        with pytest.raises(ValueError):
            model.get_feature_importance()

    def test_get_feature_importance_sklearn(self, mock_config):
        model = RentCostModel(mock_config)

        model.model = MagicMock()
        model.model.feature_importances_ = np.array([0.5, 0.3, 0.2])
        model.feature_names = ['year', 'mileage', 'brand']

        importance = model.get_feature_importance()

        assert len(importance) == 3
        assert 'feature' in importance.columns
        assert 'importance' in importance.columns

    def test_get_feature_importance_catboost(self, mock_config):
        """CatBoost expose get_feature_importance() plutôt que feature_importances_"""
        config = {**mock_config, "model_type": "catboost"}
        model = RentCostModel(config)

        model.model = MagicMock(spec=['get_feature_importance'])
        model.model.get_feature_importance.return_value = np.array([0.6, 0.4])
        model.feature_names = ['segment', 'motor_power']

        importance = model.get_feature_importance()

        assert len(importance) == 2
        model.model.get_feature_importance.assert_called_once()

    # ------------------------------------------------------------------
    # SAVE MODEL
    # ------------------------------------------------------------------

    @patch('soongo_data.utils.rent_cost_training.model_training.onnx.save_model')
    @patch('soongo_data.utils.rent_cost_training.model_training.convert_sklearn')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.mkdir')
    def test_save_model_default(self, mock_mkdir, mock_file, mock_convert, mock_save, mock_config):
        """Test sauvegarde du modèle (hist_gradient_boosting -> ONNX)"""
        model = RentCostModel(mock_config)
        model.model = MagicMock()
        model.feature_names = ['year', 'mileage']
        model.categorical_features = []
        model.numeric_features = ['year', 'mileage']
        model.metrics = {'cv_rmse_mean': 10.5}
        model.scaler = MagicMock()
        model.scaler.mean_ = np.array([2020, 15000])
        model.scaler.scale_ = np.array([1, 5000])
        model.scaler.var_ = np.array([1, 25000000])
        model.scaler.with_mean = True
        model.scaler.with_std = True
        model.scaler.n_features_in_ = 2
        model.label_encoders = {}

        mock_convert.return_value = MagicMock()

        results = {'train_metrics': {}}
        config = mock_config

        model_path = model.save_model(results, config)

        assert model_path is not None
        mock_convert.assert_called_once()
        mock_save.assert_called_once()

    @patch('soongo_data.utils.rent_cost_training.model_training.onnx.save_model')
    @patch('soongo_data.utils.rent_cost_training.model_training.convert_sklearn')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.mkdir')
    def test_save_model_catboost(self, mock_mkdir, mock_file, mock_convert, mock_save, mock_config):
        """Test sauvegarde CatBoost : format natif .cbm, pas d'export ONNX,
        pas de scaler.json ni de label_encoders.json."""
        config = {**mock_config, "model_type": "catboost"}
        model = RentCostModel(config)
        model.model = MagicMock()
        model.feature_names = ['segment', 'motor_power']
        model.categorical_features = ['segment']
        model.numeric_features = ['motor_power']
        model.metrics = {'cv_rmse_mean': 40.0}
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
        """Test suppression du dossier modèle"""
        model = RentCostModel(mock_config)

        model.remove_model_folder_from_local()

        mock_rmtree.assert_called_once()

    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    @patch('pathlib.Path.mkdir')
    def test_generate_evaluation_figures(self, mock_mkdir, mock_close, mock_savefig, mock_config):
        """Test génération des figures"""
        model = RentCostModel(mock_config)
        model.model = MagicMock()
        model.model.predict.return_value = np.array([500, 600, 550])
        model.feature_names = ['year', 'mileage']
        model.numeric_features = ['year', 'mileage']
        model.categorical_features = []
        model.label_encoders = {}
        model.scaler = MagicMock()
        model.scaler.transform.return_value = np.array([[2020, 10000], [2019, 20000], [2021, 5000]])
        model.get_feature_importance = MagicMock(return_value=pd.DataFrame())

        X_test = pd.DataFrame({'year': [2020, 2019, 2021], 'mileage': [10000, 20000, 5000]})
        y_test = pd.Series([500, 600, 550])

        model.generate_evaluation_figures(X_test, y_test)

        # Vérifie qu'au moins 4 figures sont sauvegardées
        assert mock_savefig.call_count >= 4