"""
Tests unitaires pour model_training.py - Sell Cost (Rebate Price)
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from soongo_data.utils.sell_cost_training.model_training import SellCostModel


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
    """DataFrame de target de test"""
    return pd.DataFrame({
        'vehicle_id': ['v1', 'v2', 'v3', 'v4', 'v5'],
        'target':     [25000, 32000, 28000, 26000, 30000]
    })


class TestSellCostModel:
    """Tests pour SellCostModel"""

    def test_init(self, mock_config):
        """Test initialisation du modèle"""
        model = SellCostModel(mock_config)

        assert model.model_type == "hist_gradient_boosting"
        assert model.test_size == 0.3
        assert model.random_state == 42
        assert model.model is None
        assert model.feature_importance == {}

    def test_get_model(self, mock_config):
        """Test récupération du modèle"""
        model = SellCostModel(mock_config)

        base_model = model._get_model()

        assert base_model is not None
        assert hasattr(base_model, 'fit')

    def test_preprocess_features_fit(self, mock_config, sample_features):
        """Test preprocessing avec fit"""
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
        """Test preprocessing sans fit"""
        model = SellCostModel(mock_config)
        feature_list = ['brand', 'entry_year', 'age', 'energy', 'fiscal_power',
                        'seat_count', 'transmission', 'motor_power', 'segment']

        model.preprocess_features(sample_features, feature_list, fit=True)
        X = model.preprocess_features(sample_features, feature_list, fit=False)

        assert X.shape[0] == 5
        assert X.shape[1] == len(feature_list)

    def test_prepare_train_test_split(self, mock_config, sample_features, sample_target):
        """Test split train/test"""
        model = SellCostModel(mock_config)

        X_train, X_test, y_train, y_test = model.prepare_train_test_split(
            sample_features, sample_target, test_size=0.3, random_state=42
        )

        assert len(X_train) + len(X_test) == 5
        assert len(y_train) + len(y_test) == 5
        assert 'vehicle_id' not in X_train.columns

    @patch('soongo_data.utils.sell_cost_training.model_training.cross_val_score')
    def test_model_fit(self, mock_cv_score, mock_config):
        """Test entraînement du modèle"""
        model = SellCostModel(mock_config)

        mock_cv_score.return_value = np.array([0.8, 0.85, 0.82, 0.88, 0.84])

        X_train = pd.DataFrame({
            'brand':        ['Toyota', 'Ford', 'Honda'],
            'entry_year':   [2020, 2019, 2021],
            'age':          [6, 7, 5],
            'fiscal_power': [6.0, 7.0, 5.0],
            'motor_power':  [110.0, 130.0, 150.0],
        })
        y_train = pd.Series([25000, 32000, 28000])

        metrics = model.model_fit(X_train, y_train)

        assert 'cv_rmse_mean' in metrics
        assert 'cv_mae_mean' in metrics
        assert 'cv_r2_mean' in metrics
        assert model.model is not None

    def test_evaluate(self, mock_config):
        """Test évaluation du modèle"""
        model = SellCostModel(mock_config)

        model.feature_names    = ['entry_year', 'age', 'fiscal_power', 'motor_power']
        model.numeric_features = ['entry_year', 'age', 'fiscal_power', 'motor_power']
        model.categorical_features = []
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

        assert 'train_mae'  in metrics
        assert 'test_mae'   in metrics
        assert 'train_r2'   in metrics
        assert 'test_r2'    in metrics
        assert 'train_rmse' in metrics
        assert 'test_rmse'  in metrics

    def test_get_feature_importance(self, mock_config):
        """Test récupération importance des features"""
        model = SellCostModel(mock_config)

        # Model non entraîné → ValueError
        with pytest.raises(ValueError):
            model.get_feature_importance()

        # Model avec feature_importances_
        model.model = MagicMock()
        model.model.feature_importances_ = np.array([0.4, 0.3, 0.15, 0.1, 0.05])
        model.feature_names = ['entry_year', 'age', 'brand', 'fiscal_power', 'motor_power']

        importance = model.get_feature_importance()

        assert len(importance) == 5
        assert 'feature'    in importance.columns
        assert 'importance' in importance.columns
        # Vérifie le tri décroissant
        assert importance.iloc[0]['importance'] >= importance.iloc[1]['importance']

    @patch('soongo_data.utils.sell_cost_training.model_training.onnx.save_model')
    @patch('soongo_data.utils.sell_cost_training.model_training.convert_sklearn')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.mkdir')
    def test_save_model(self, mock_mkdir, mock_file, mock_convert, mock_save, mock_config):
        """Test sauvegarde du modèle"""
        model = SellCostModel(mock_config)
        model.model              = MagicMock()
        model.feature_names      = ['entry_year', 'age', 'fiscal_power', 'motor_power']
        model.categorical_features = []
        model.numeric_features   = ['entry_year', 'age', 'fiscal_power', 'motor_power']
        model.metrics            = {'cv_rmse_mean': 1500.0}
        model.feature_importance = {'entry_year': 0.4, 'age': 0.3,
                                    'fiscal_power': 0.2, 'motor_power': 0.1}
        model.scaler             = MagicMock()
        model.scaler.mean_       = np.array([2020, 6, 6.0, 110.0])
        model.scaler.scale_      = np.array([2.0, 1.5, 1.0, 20.0])
        model.scaler.var_        = np.array([4.0, 2.25, 1.0, 400.0])
        model.scaler.with_mean   = True
        model.scaler.with_std    = True
        model.scaler.n_features_in_ = 4
        model.label_encoders     = {}

        mock_convert.return_value = MagicMock()

        model_path = model.save_model({'train_metrics': {}}, mock_config)

        assert model_path is not None
        mock_convert.assert_called_once()
        mock_save.assert_called_once()

    @patch('shutil.rmtree')
    def test_remove_model_folder(self, mock_rmtree, mock_config):
        """Test suppression du dossier modèle"""
        model = SellCostModel(mock_config)

        model.remove_model_folder_from_local()

        mock_rmtree.assert_called_once()

    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    @patch('pathlib.Path.mkdir')
    def test_generate_evaluation_figures(self, mock_mkdir, mock_close, mock_savefig, mock_config):
        """Test génération des figures"""
        model = SellCostModel(mock_config)
        model.model              = MagicMock()
        model.model.predict.return_value = np.array([25000, 32000, 28000])
        model.feature_names      = ['entry_year', 'age', 'fiscal_power', 'motor_power']
        model.numeric_features   = ['entry_year', 'age', 'fiscal_power', 'motor_power']
        model.categorical_features = []
        model.scaler             = MagicMock()
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