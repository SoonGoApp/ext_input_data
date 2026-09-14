"""
Tests unitaires pour model_predict.py - Sell Cost Predict
"""

import json
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, mock_open
from soongo_data.utils.sell_cost_predict.model_predict import SellCostPredictor


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
        'brand':        ['Toyota', 'Ford', 'Honda'],
        'entry_year':   [2020, 2019, 2021],
        'age':          [6, 7, 5],
        'segment':      ['SUV', 'Berline', 'SUV'],
        'energy':       ['Diesel', 'Petrol', 'Electric'],
        'fiscal_power': [6.0, 7.0, 5.0],
        'seat_count':   [5.0, 5.0, 5.0],
        'transmission': ['Manual', 'Auto', 'Auto'],
        'motor_power':  [110.0, 130.0, 150.0],
    })


@pytest.fixture
def mock_model_artifacts():
    return {
        "metadata": {
            "model_type": "hist_gradient_boosting",
            "feature_names": ["brand", "entry_year", "age", "segment", "energy",
                               "fiscal_power", "seat_count", "transmission", "motor_power"],
            "categorical_features": ["brand", "segment", "energy", "transmission"],
            "numeric_features": ["entry_year", "age", "fiscal_power", "seat_count", "motor_power"],
            "metrics": {"test_mae": 1500.0},
            "median_values": {}
        },
        "scaler": {
            "scaler_type": "StandardScaler",
            "mean":  [2020.0, 6.0, 6.0, 5.0, 110.0, 0, 0, 0, 0],
            "scale": [2.0, 1.5, 1.0, 1.0, 20.0, 1, 1, 1, 1],
            "var":   [4.0, 2.25, 1.0, 1.0, 400.0, 1, 1, 1, 1],
            "with_mean": True,
            "with_std": True,
            "n_features": 9
        },
        "encoders": {
            "brand":        {"classes": ["Toyota", "Ford", "Honda"]},
            "segment":      {"classes": ["SUV", "Berline"]},
            "energy":       {"classes": ["Diesel", "Petrol", "Electric"]},
            "transmission": {"classes": ["Manual", "Auto"]}
        }
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


class TestSellCostPredictor:
    """Tests pour SellCostPredictor"""

    @patch('soongo_data.utils.sell_cost_predict.model_predict.pull_folder_from_s3')
    @patch('soongo_data.utils.sell_cost_predict.model_predict.s3_get_most_recent_folder')
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('soongo_data.utils.sell_cost_predict.model_predict.ort.InferenceSession')
    def test_init(self, mock_ort, mock_file, mock_exists, mock_s3_recent, mock_pull_s3, mock_config, mock_model_artifacts):
        """Test initialisation du predictor"""
        mock_s3_recent.return_value = "model_2024-01-01"
        mock_exists.return_value = True
        mock_file.side_effect = _open_side_effect(mock_model_artifacts)

        predictor = SellCostPredictor(mock_config)

        assert predictor.config == mock_config
        assert predictor.model_type == "hist_gradient_boosting"
        mock_pull_s3.assert_called_once()

    @patch('soongo_data.utils.sell_cost_predict.model_predict.pull_folder_from_s3')
    @patch('soongo_data.utils.sell_cost_predict.model_predict.s3_get_most_recent_folder')
    def test_load_model_from_s3(self, mock_s3_recent, mock_pull_s3, mock_config):
        """Test chargement du modèle depuis S3"""
        mock_s3_recent.return_value = "model_2024-01-01"

        with patch.object(SellCostPredictor, 'load_model_artifacts'):
            predictor = SellCostPredictor.__new__(SellCostPredictor)
            predictor.config = mock_config

            result = predictor.load_model_from_s3()

            assert "model_2024-01-01" in str(result)
            mock_s3_recent.assert_called_once()
            mock_pull_s3.assert_called_once()

    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('soongo_data.utils.sell_cost_predict.model_predict.ort.InferenceSession')
    def test_load_model_artifacts_success(self, mock_ort, mock_file, mock_exists, mock_model_artifacts):
        """Test chargement des artifacts avec succès"""
        mock_exists.return_value = True
        mock_file.side_effect = _open_side_effect(mock_model_artifacts)

        predictor = SellCostPredictor.__new__(SellCostPredictor)
        predictor.load_model_artifacts("/tmp/model")

        assert predictor.model_type == "hist_gradient_boosting"
        assert "entry_year" in predictor.feature_names
        assert "age" in predictor.feature_names
        assert predictor.scaler is not None

    @patch('pathlib.Path.exists')
    def test_load_model_artifacts_file_not_found(self, mock_exists):
        """Test échec si modèle non trouvé"""
        mock_exists.return_value = False

        predictor = SellCostPredictor.__new__(SellCostPredictor)

        with pytest.raises(FileNotFoundError):
            predictor.load_model_artifacts("/tmp/model")

    @patch('shutil.rmtree')
    def test_remove_model_folder(self, mock_rmtree, mock_config):
        """Test suppression du dossier modèle"""
        with patch.object(SellCostPredictor, '__init__', lambda x, y: None):
            predictor = SellCostPredictor(None)
            predictor.config = mock_config

            predictor.remove_model_folder_from_local()

            mock_rmtree.assert_called_once()

    # ------------------------------------------------------------------
    # PREPROCESS
    # ------------------------------------------------------------------

    def test_preprocess_features(self, sample_features):
        """Test preprocessing des features (path ONNX / scaler)"""
        with patch.object(SellCostPredictor, '__init__', lambda x, y: None):
            predictor = SellCostPredictor(None)
            predictor.model_type = "hist_gradient_boosting"
            predictor.categorical_features = ['brand', 'segment', 'energy', 'transmission']
            predictor.numeric_features = ['entry_year', 'age', 'fiscal_power', 'seat_count', 'motor_power']
            predictor.std_nb = 5

            predictor.scaler = MagicMock()
            predictor.scaler.mean_ = np.zeros(9)
            predictor.scaler.scale_ = np.ones(9)
            predictor.scaler.transform.return_value = np.zeros((3, 9), dtype=np.float32)

            mock_encoder = MagicMock()
            mock_encoder.transform.return_value = np.array([[0], [1], [2]])
            predictor.label_encoders = {
                'brand': mock_encoder,
                'segment': mock_encoder,
                'energy': mock_encoder,
                'transmission': mock_encoder,
            }

            feature_list = ['brand', 'entry_year', 'age', 'segment', 'energy',
                             'fiscal_power', 'seat_count', 'transmission', 'motor_power']
            result = predictor.preprocess_features(sample_features, feature_list)

            assert result.shape[0] == 3
            predictor.scaler.transform.assert_called_once()

    def test_preprocess_features_missing_columns_raises(self, sample_features):
        """Test qu'une colonne manquante lève ValueError"""
        with patch.object(SellCostPredictor, '__init__', lambda x, y: None):
            predictor = SellCostPredictor(None)
            predictor.model_type = "hist_gradient_boosting"
            predictor.categorical_features = []
            predictor.label_encoders = {}

            with pytest.raises(ValueError):
                predictor.preprocess_features(sample_features, ['brand', 'not_a_column'])

    def test_preprocess_features_catboost_no_encoding(self, sample_features):
        """Test que pour CatBoost, aucun encodage/scaling n'est appliqué"""
        with patch.object(SellCostPredictor, '__init__', lambda x, y: None):
            predictor = SellCostPredictor(None)
            predictor.model_type = "catboost"

            feature_list = ['brand', 'entry_year']
            result = predictor.preprocess_features(sample_features, feature_list)

            assert isinstance(result, pd.DataFrame)
            assert list(result.columns) == feature_list
            assert list(result['brand']) == ['Toyota', 'Ford', 'Honda']

    def test_preprocess_features_missing_encoder_raises(self, sample_features):
        """Test qu'une feature catégorielle sans label encoder chargé lève ValueError"""
        with patch.object(SellCostPredictor, '__init__', lambda x, y: None):
            predictor = SellCostPredictor(None)
            predictor.model_type = "hist_gradient_boosting"
            predictor.categorical_features = ['brand']
            predictor.label_encoders = {}  # pas d'encoder pour 'brand'

            with pytest.raises(ValueError):
                predictor.preprocess_features(sample_features, ['brand', 'entry_year'])

    # ------------------------------------------------------------------
    # PREDICT
    # ------------------------------------------------------------------

    def test_predict_success(self, sample_features):
        """Test prédiction ONNX avec succès"""
        with patch.object(SellCostPredictor, '__init__', lambda x, y: None):
            predictor = SellCostPredictor(None)
            predictor.model_type = "hist_gradient_boosting"
            predictor.feature_names = ['brand', 'entry_year', 'age', 'segment',
                                        'energy', 'fiscal_power', 'seat_count',
                                        'transmission', 'motor_power']
            predictor.categorical_features = ['brand', 'segment', 'energy', 'transmission']
            predictor.numeric_features = ['entry_year', 'age', 'fiscal_power',
                                           'seat_count', 'motor_power']
            predictor.std_nb = 5

            predictor.model = MagicMock()
            predictor.model.get_inputs.return_value = [MagicMock(name='float_input')]
            predictor.model.run.return_value = [np.array([[25000], [32000], [28000]])]

            predictor.preprocess_features = MagicMock(
                return_value=np.zeros((3, 9), dtype=np.float32)
            )

            result = predictor.predict(sample_features)

            assert len(result) == 3
            predictor.model.run.assert_called_once()

    def test_predict_model_not_trained(self, sample_features):
        """Test prédiction sans modèle chargé"""
        with patch.object(SellCostPredictor, '__init__', lambda x, y: None):
            predictor = SellCostPredictor(None)
            predictor.model = None

            with pytest.raises(ValueError):
                predictor.predict(sample_features)

    def test_predict_onnx_error(self, sample_features):
        """Test erreur ONNX pendant la prédiction"""
        with patch.object(SellCostPredictor, '__init__', lambda x, y: None):
            predictor = SellCostPredictor(None)
            predictor.model_type = "hist_gradient_boosting"
            predictor.feature_names = ['brand', 'entry_year', 'age']
            predictor.model = MagicMock()
            predictor.model.get_inputs.return_value = [MagicMock(name='float_input')]
            predictor.model.run.side_effect = Exception("ONNX error")
            predictor.preprocess_features = MagicMock(
                return_value=np.zeros((3, 3), dtype=np.float32)
            )

            with pytest.raises(Exception):
                predictor.predict(sample_features)

    def test_predict_output_flattened(self, sample_features):
        """Test que la sortie est bien un array 1D"""
        with patch.object(SellCostPredictor, '__init__', lambda x, y: None):
            predictor = SellCostPredictor(None)
            predictor.model_type = "hist_gradient_boosting"
            predictor.feature_names = ['brand', 'entry_year', 'age']
            predictor.model = MagicMock()
            predictor.model.get_inputs.return_value = [MagicMock(name='float_input')]
            predictor.model.run.return_value = [np.array([[25000], [32000], [28000]])]
            predictor.preprocess_features = MagicMock(
                return_value=np.zeros((3, 3), dtype=np.float32)
            )

            result = predictor.predict(sample_features)

            assert result.ndim == 1
            assert list(result) == [25000, 32000, 28000]

    def test_predict_catboost(self, sample_features):
        """Test prédiction CatBoost (Pool construit avec les bons cat_features)"""
        with patch.object(SellCostPredictor, '__init__', lambda x, y: None), \
             patch('catboost.Pool') as mock_pool_cls:
            predictor = SellCostPredictor(None)
            predictor.model_type = "catboost"
            predictor.feature_names = ['brand', 'entry_year', 'motor_power']
            predictor.categorical_features = ['brand']

            predictor.model = MagicMock()
            predictor.model.predict.return_value = np.array([25000.0, 32000.0, 28000.0])

            predictor.preprocess_features = MagicMock(
                return_value=sample_features[['brand', 'entry_year', 'motor_power']]
            )

            result = predictor.predict(sample_features)

            assert len(result) == 3
            mock_pool_cls.assert_called_once()
            _, pool_kwargs = mock_pool_cls.call_args
            assert pool_kwargs.get('cat_features') == [0]