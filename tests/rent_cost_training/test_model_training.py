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
        "model_params": {
            "max_iter": 100,
            "random_state": 42
        }
    }


@pytest.fixture
def sample_features():
    """DataFrame de features de test"""
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


class TestRentCostModel:
    """Tests pour RentCostModel"""

    def test_init(self, mock_config):
        """Test initialisation du modèle"""
        model = RentCostModel(mock_config)
        
        assert model.model_type == "hist_gradient_boosting"
        assert model.test_size == 0.3
        assert model.random_state == 42
        assert model.model is None

    def test_get_model(self, mock_config):
        """Test récupération du modèle"""
        model = RentCostModel(mock_config)
        
        base_model = model._get_model()
        
        assert base_model is not None
        assert hasattr(base_model, 'fit')

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
        
        # Fit first
        model.preprocess_features(sample_features, feature_list, fit=True)
        
        # Transform
        X = model.preprocess_features(sample_features, feature_list, fit=False)
        
        assert X.shape[0] == 5
        assert X.shape[1] == 4

    def test_prepare_train_test_split(self, mock_config, sample_features, sample_target):
        """Test split train/test"""
        model = RentCostModel(mock_config)
        
        X_train, X_test, y_train, y_test = model.prepare_train_test_split(
            sample_features, sample_target, test_size=0.3, random_state=42
        )
        
        assert len(X_train) + len(X_test) == 5
        assert len(y_train) + len(y_test) == 5
        assert 'vehicle_id' not in X_train.columns

    @patch('soongo_data.utils.rent_cost_training.model_training.cross_val_score')
    def test_model_fit(self, mock_cv_score, mock_config):
        """Test entraînement du modèle"""
        model = RentCostModel(mock_config)
        
        # Mock cross-validation scores
        mock_cv_score.return_value = np.array([0.8, 0.85, 0.82, 0.88, 0.84])
        
        X_train = pd.DataFrame({
            'brand': ['Toyota', 'Ford', 'Honda'],
            'year': [2020, 2019, 2021],
            'mileage': [10000, 20000, 5000]
        })
        y_train = pd.Series([500, 600, 550])
        
        metrics = model.model_fit(X_train, y_train)
        
        assert 'cv_rmse_mean' in metrics
        assert 'cv_mae_mean' in metrics
        assert 'cv_r2_mean' in metrics
        assert model.model is not None

    def test_evaluate(self, mock_config):
        """Test évaluation du modèle"""
        model = RentCostModel(mock_config)
        
        # Setup model
        model.feature_names = ['year', 'mileage']
        model.numeric_features = ['year', 'mileage']
        model.categorical_features = []
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

    def test_get_feature_importance(self, mock_config):
        """Test récupération importance des features"""
        model = RentCostModel(mock_config)
        
        # Model sans feature_importances_
        with pytest.raises(ValueError):
            model.get_feature_importance()
        
        # Model avec feature_importances_
        model.model = MagicMock()
        model.model.feature_importances_ = np.array([0.5, 0.3, 0.2])
        model.feature_names = ['year', 'mileage', 'brand']
        
        importance = model.get_feature_importance()
        
        assert len(importance) == 3
        assert 'feature' in importance.columns
        assert 'importance' in importance.columns

    @patch('soongo_data.utils.rent_cost_training.model_training.onnx.save_model')
    @patch('soongo_data.utils.rent_cost_training.model_training.convert_sklearn')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.mkdir')
    def test_save_model(self, mock_mkdir, mock_file, mock_convert, mock_save, mock_config):
        """Test sauvegarde du modèle"""
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
        model.scaler = MagicMock()
        model.scaler.transform.return_value = np.array([[2020, 10000], [2019, 20000], [2021, 5000]])
        model.get_feature_importance = MagicMock(return_value=pd.DataFrame())
        
        X_test = pd.DataFrame({'year': [2020, 2019, 2021], 'mileage': [10000, 20000, 5000]})
        y_test = pd.Series([500, 600, 550])
        
        model.generate_evaluation_figures(X_test, y_test)
        
        # Vérifie qu'au moins 4 figures sont sauvegardées
        assert mock_savefig.call_count >= 4