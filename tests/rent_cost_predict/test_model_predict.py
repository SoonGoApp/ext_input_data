"""
Tests unitaires pour model_predict.py
"""

import json
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, mock_open
from soongo_data.utils.rent_cost_predict.model_predict import RentalCostPredictor


@pytest.fixture
def mock_config():
    return {
        "bucket_name": "test-bucket",
        "model_folder": "models",
        "models_dir": "/tmp/models"
    }


@pytest.fixture
def sample_features():
    return pd.DataFrame({
        'vehicle_id': ['v1', 'v2', 'v3'],
        'brand': ['Toyota', 'Ford', 'Honda'],
        'year': [2020, 2019, 2021],
        'mileage': [10000, 20000, 5000]
    })


@pytest.fixture
def mock_model_artifacts():
    return {
        "metadata": {
            "model_type": "hist_gradient_boosting",
            "format": "onnx",
            "feature_names": ["brand", "year", "mileage"],
            "categorical_features": ["brand"],
            "numeric_features": ["year", "mileage"],
            "metrics": {"test_mae": 10.5},
            "median_values": {}
        },
        "scaler": {
            "scaler_type": "StandardScaler",
            "mean": [2020.0, 15000.0],
            "scale": [1.0, 5000.0],
            "var": [1.0, 25000000.0],
            "with_mean": True,
            "with_std": True,
            "n_features": 2
        },
        "encoders": {
            "brand": {"classes": ["Toyota", "Ford", "Honda"]}
        }
    }


@pytest.fixture
def mock_catboost_metadata():
    return {
        "model_type": "catboost",
        "format": "cbm",
        "feature_names": ["brand", "year", "mileage"],
        "categorical_features": ["brand"],
        "numeric_features": ["year", "mileage"],
        "metrics": {"test_mae": 8.2},
        "median_values": {}
    }


def _open_side_effect(artifacts):
    def _side_effect(*args, **kwargs):
        filename = str(args[0])
        if 'metadata.json' in filename:
            return mock_open(read_data=json.dumps(artifacts["metadata"]))()
        elif 'scaler.json' in filename:
            return mock_open(read_data=json.dumps(artifacts["scaler"]))()
        elif 'label_encoders.json' in filename:
            return mock_open(read_data=json.dumps(artifacts["encoders"]))()
        return mock_open()()
    return _side_effect


class TestRentalCostPredictor:
    """Tests pour RentalCostPredictor"""

    # ------------------------------------------------------------------
    # INIT / S3
    # ------------------------------------------------------------------

    @patch('soongo_data.utils.rent_cost_predict.model_predict.pull_folder_from_s3')
    @patch('soongo_data.utils.rent_cost_predict.model_predict.s3_get_most_recent_folder')
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('soongo_data.utils.rent_cost_predict.model_predict.ort.InferenceSession')
    def test_init(self, mock_ort, mock_file, mock_exists, mock_s3_recent, mock_pull_s3, mock_config, mock_model_artifacts):
        """Test initialisation du predictor (format onnx)"""
        mock_s3_recent.return_value = "model_2024-01-01"
        mock_exists.return_value = True
        mock_file.side_effect = _open_side_effect(mock_model_artifacts)

        predictor = RentalCostPredictor(mock_config)

        assert predictor.config == mock_config
        assert predictor.model_type == "hist_gradient_boosting"
        assert predictor.model_format == "onnx"
        mock_pull_s3.assert_called_once()

    @patch('soongo_data.utils.rent_cost_predict.model_predict.pull_folder_from_s3')
    @patch('soongo_data.utils.rent_cost_predict.model_predict.s3_get_most_recent_folder')
    def test_load_model_from_s3(self, mock_s3_recent, mock_pull_s3, mock_config):
        """Test chargement du modèle depuis S3"""
        mock_s3_recent.return_value = "model_2024-01-01"

        with patch.object(RentalCostPredictor, 'load_model_artifacts'):
            predictor = RentalCostPredictor.__new__(RentalCostPredictor)
            predictor.config = mock_config

            result = predictor.load_model_from_s3()

            assert "model_2024-01-01" in str(result)
            mock_s3_recent.assert_called_once()
            mock_pull_s3.assert_called_once()

    # ------------------------------------------------------------------
    # LOAD ARTIFACTS - ONNX
    # ------------------------------------------------------------------

    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('soongo_data.utils.rent_cost_predict.model_predict.ort.InferenceSession')
    def test_load_model_artifacts_onnx_success(self, mock_ort, mock_file, mock_exists, mock_model_artifacts):
        """Test chargement des artifacts ONNX avec succès"""
        mock_exists.return_value = True
        mock_file.side_effect = _open_side_effect(mock_model_artifacts)

        predictor = RentalCostPredictor.__new__(RentalCostPredictor)
        predictor.load_model_artifacts("/tmp/model")

        assert predictor.model_type == "hist_gradient_boosting"
        assert predictor.model_format == "onnx"
        assert predictor.feature_names == ["brand", "year", "mileage"]
        assert predictor.scaler is not None
        assert predictor.label_encoders is not None

    @patch('pathlib.Path.exists')
    def test_load_model_artifacts_file_not_found(self, mock_exists):
        """Test échec si dossier modèle non trouvé"""
        mock_exists.return_value = False

        predictor = RentalCostPredictor.__new__(RentalCostPredictor)

        with pytest.raises(FileNotFoundError):
            predictor.load_model_artifacts("/tmp/model")

    # ------------------------------------------------------------------
    # LOAD ARTIFACTS - CATBOOST
    # ------------------------------------------------------------------

    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('catboost.CatBoostRegressor')
    def test_load_model_artifacts_catboost(self, mock_catboost_cls, mock_file, mock_exists, mock_catboost_metadata):
        """Test chargement des artifacts CatBoost (.cbm) : pas de scaler ni d'encoders"""
        mock_exists.return_value = True
        mock_file.side_effect = _open_side_effect({"metadata": mock_catboost_metadata})
        mock_catboost_cls.return_value = MagicMock()

        predictor = RentalCostPredictor.__new__(RentalCostPredictor)
        predictor.load_model_artifacts("/tmp/model")

        assert predictor.model_type == "catboost"
        assert predictor.model_format == "cbm"
        assert predictor.scaler is None
        assert predictor.label_encoders is None
        predictor.model.load_model.assert_called_once()
        call_kwargs = predictor.model.load_model.call_args.kwargs
        assert call_kwargs.get('format') == 'cbm'

    # ------------------------------------------------------------------
    # CLEANUP
    # ------------------------------------------------------------------

    @patch('shutil.rmtree')
    def test_remove_model_folder(self, mock_rmtree, mock_config):
        """Test suppression du dossier modèle"""
        with patch.object(RentalCostPredictor, '__init__', lambda x, y: None):
            predictor = RentalCostPredictor(None)
            predictor.config = mock_config

            predictor.remove_model_folder_from_local()

            mock_rmtree.assert_called_once()

    # ------------------------------------------------------------------
    # PREPROCESS (ONNX path)
    # ------------------------------------------------------------------

    def test_preprocess_features(self, sample_features):
        """Test preprocessing des features (path ONNX)"""
        with patch.object(RentalCostPredictor, '__init__', lambda x, y: None):
            predictor = RentalCostPredictor(None)
            predictor.categorical_features = ['brand']
            predictor.numeric_features = ['year', 'mileage']
            predictor.std_nb = 5

            predictor.scaler = MagicMock()
            predictor.scaler.transform.return_value = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])

            mock_encoder = MagicMock()
            mock_encoder.transform.return_value = np.array([[0], [1], [2]])
            predictor.label_encoders = {'brand': mock_encoder}

            feature_list = ['brand', 'year', 'mileage']
            result = predictor.preprocess_features(sample_features, feature_list)

            assert result.shape[0] == 3
            predictor.scaler.transform.assert_called_once()

    # ------------------------------------------------------------------
    # PREDICT - dispatch / ONNX / CatBoost
    # ------------------------------------------------------------------

    def test_predict_model_not_trained(self, sample_features):
        """Test prédiction sans modèle chargé"""
        with patch.object(RentalCostPredictor, '__init__', lambda x, y: None):
            predictor = RentalCostPredictor(None)
            predictor.model = None

            with pytest.raises(ValueError):
                predictor.predict(sample_features)

    def test_predict_dispatches_to_onnx(self, sample_features):
        """model_format='onnx' -> _predict_onnx doit être appelé"""
        with patch.object(RentalCostPredictor, '__init__', lambda x, y: None):
            predictor = RentalCostPredictor(None)
            predictor.model = MagicMock()
            predictor.model_format = "onnx"
            predictor._predict_onnx = MagicMock(return_value=np.array([1.0]))
            predictor._predict_catboost = MagicMock()

            predictor.predict(sample_features)

            predictor._predict_onnx.assert_called_once()
            predictor._predict_catboost.assert_not_called()

    def test_predict_dispatches_to_catboost(self, sample_features):
        """model_format='cbm' -> _predict_catboost doit être appelé"""
        with patch.object(RentalCostPredictor, '__init__', lambda x, y: None):
            predictor = RentalCostPredictor(None)
            predictor.model = MagicMock()
            predictor.model_format = "cbm"
            predictor._predict_onnx = MagicMock()
            predictor._predict_catboost = MagicMock(return_value=np.array([1.0]))

            predictor.predict(sample_features)

            predictor._predict_catboost.assert_called_once()
            predictor._predict_onnx.assert_not_called()

    def test_predict_onnx_success(self, sample_features):
        """Test prédiction ONNX bout-en-bout"""
        with patch.object(RentalCostPredictor, '__init__', lambda x, y: None):
            predictor = RentalCostPredictor(None)
            predictor.model_format = "onnx"
            predictor.feature_names = ['brand', 'year', 'mileage']
            predictor.categorical_features = ['brand']
            predictor.numeric_features = ['year', 'mileage']
            predictor.std_nb = 5

            predictor.model = MagicMock()
            predictor.model.get_inputs.return_value = [MagicMock(name='float_input')]
            predictor.model.run.return_value = [np.array([[500], [600], [550]])]

            predictor.preprocess_features = MagicMock(
                return_value=np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]], dtype=np.float32)
            )

            result = predictor.predict(sample_features)

            assert len(result) == 3
            predictor.model.run.assert_called_once()

    def test_predict_onnx_error(self, sample_features):
        """Test erreur ONNX pendant la prédiction"""
        with patch.object(RentalCostPredictor, '__init__', lambda x, y: None):
            predictor = RentalCostPredictor(None)
            predictor.model_format = "onnx"
            predictor.feature_names = ['brand', 'year', 'mileage']
            predictor.model = MagicMock()
            predictor.model.get_inputs.return_value = [MagicMock(name='float_input')]
            predictor.model.run.side_effect = Exception("ONNX error")
            predictor.preprocess_features = MagicMock(return_value=np.array([[0.1, 0.2]], dtype=np.float32))

            with pytest.raises(Exception):
                predictor.predict(sample_features)

    def test_predict_catboost_success(self, sample_features):
        """Test prédiction CatBoost bout-en-bout (Pool construit avec les bons cat_features)"""
        with patch.object(RentalCostPredictor, '__init__', lambda x, y: None), \
             patch('catboost.Pool') as mock_pool_cls:
            predictor = RentalCostPredictor(None)
            predictor.model_format = "cbm"
            predictor.feature_names = ['brand', 'year', 'mileage']
            predictor.categorical_features = ['brand']

            predictor.model = MagicMock()
            predictor.model.predict.return_value = np.array([500.0, 600.0, 550.0])

            X = sample_features.drop(columns=['vehicle_id'])
            result = predictor.predict(X)

            assert len(result) == 3
            mock_pool_cls.assert_called_once()
            _, pool_kwargs = mock_pool_cls.call_args
            assert pool_kwargs.get('cat_features') == [0]  # index de 'brand' dans feature_names
            predictor.model.predict.assert_called_once()