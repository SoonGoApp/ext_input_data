"""
Tests unitaires pour inference_pipeline.py
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from soongo_data.utils.rent_cost_predict.inference_pipeline import (
    InferencePipeline,
    run_pipeline
)


@pytest.fixture
def mock_config():
    """Configuration de test"""
    return {
        "bucket_name": "test-bucket",
        "model_folder": "models",
        "models_dir": "/tmp/models"
    }


@pytest.fixture
def sample_features():
    """Features de test"""
    return pd.DataFrame({
        'vehicle_id': ['v1', 'v2', 'v3'],
        'brand': ['Toyota', 'Ford', 'Honda'],
        'year': [2020, 2019, 2021],
        'mileage': [10000, 20000, 5000]
    })


@pytest.fixture
def sample_predictions():
    """Prédictions de test"""
    return np.array([500, 600, 550])


class TestInferencePipeline:
    """Tests pour InferencePipeline"""

    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.RentalCostPredictor')
    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.DataLoader')
    def test_init(self, mock_data_loader, mock_predictor, mock_config):
        """Test initialisation du pipeline"""
        mock_loader_instance = MagicMock()
        mock_data_loader.return_value = mock_loader_instance
        mock_predictor_instance = MagicMock()
        mock_predictor.return_value = mock_predictor_instance
        
        pipeline = InferencePipeline(mock_config)
        
        assert pipeline.config == mock_config
        assert pipeline.data_loader == mock_loader_instance
        assert pipeline.model == mock_predictor_instance
        assert pipeline.predictions is None

    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.RentalCostPredictor')
    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.DataLoader')
    def test_run_success(self, mock_data_loader, mock_predictor, mock_config, sample_features, sample_predictions):
        """Test exécution complète du pipeline avec succès"""
        # Setup mocks
        mock_loader_instance = MagicMock()
        mock_data_loader.return_value = mock_loader_instance
        mock_loader_instance.load_data.return_value = sample_features
        
        mock_predictor_instance = MagicMock()
        mock_predictor.return_value = mock_predictor_instance
        mock_predictor_instance.predict.return_value = sample_predictions
        mock_predictor_instance.model_type = "hist_gradient_boosting"
        
        pipeline = InferencePipeline(mock_config)
        result = pipeline.run()
        
        # Assert
        assert len(result) == 3
        assert 'vehicle_id' in result.columns
        assert 'predicted_total_rent_tax_exc' in result.columns
        assert 'model' in result.columns
        assert result['model'].iloc[0] == "hist_gradient_boosting"
        
        mock_loader_instance.load_data.assert_called_once()
        mock_predictor_instance.predict.assert_called_once()
        mock_loader_instance.write_results_to_db.assert_called_once()
        mock_predictor_instance.remove_model_folder_from_local.assert_called_once()

    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.RentalCostPredictor')
    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.DataLoader')
    def test_run_prediction_failure(self, mock_data_loader, mock_predictor, mock_config, sample_features):
        """Test échec de la prédiction"""
        # Setup mocks
        mock_loader_instance = MagicMock()
        mock_data_loader.return_value = mock_loader_instance
        mock_loader_instance.load_data.return_value = sample_features
        
        mock_predictor_instance = MagicMock()
        mock_predictor.return_value = mock_predictor_instance
        mock_predictor_instance.predict.side_effect = Exception("Prediction error")
        
        pipeline = InferencePipeline(mock_config)
        
        with pytest.raises(Exception):
            pipeline.run()

    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.RentalCostPredictor')
    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.DataLoader')
    def test_run_data_loading_failure(self, mock_data_loader, mock_predictor, mock_config):
        """Test échec du chargement des données"""
        # Setup mocks
        mock_loader_instance = MagicMock()
        mock_data_loader.return_value = mock_loader_instance
        mock_loader_instance.load_data.side_effect = Exception("Data loading error")
        
        mock_predictor_instance = MagicMock()
        mock_predictor.return_value = mock_predictor_instance
        
        pipeline = InferencePipeline(mock_config)
        
        with pytest.raises(Exception):
            pipeline.run()

    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.RentalCostPredictor')
    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.DataLoader')
    def test_run_write_failure(self, mock_data_loader, mock_predictor, mock_config, sample_features, sample_predictions):
        """Test échec de l'écriture en DB"""
        # Setup mocks
        mock_loader_instance = MagicMock()
        mock_data_loader.return_value = mock_loader_instance
        mock_loader_instance.load_data.return_value = sample_features
        mock_loader_instance.write_results_to_db.side_effect = Exception("Write error")
        
        mock_predictor_instance = MagicMock()
        mock_predictor.return_value = mock_predictor_instance
        mock_predictor_instance.predict.return_value = sample_predictions
        mock_predictor_instance.model_type = "hist_gradient_boosting"
        
        pipeline = InferencePipeline(mock_config)
        
        with pytest.raises(Exception):
            pipeline.run()

    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.RentalCostPredictor')
    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.DataLoader')
    def test_predictions_stored(self, mock_data_loader, mock_predictor, mock_config, sample_features, sample_predictions):
        """Test que les prédictions sont stockées dans l'instance"""
        # Setup mocks
        mock_loader_instance = MagicMock()
        mock_data_loader.return_value = mock_loader_instance
        mock_loader_instance.load_data.return_value = sample_features
        
        mock_predictor_instance = MagicMock()
        mock_predictor.return_value = mock_predictor_instance
        mock_predictor_instance.predict.return_value = sample_predictions
        mock_predictor_instance.model_type = "hist_gradient_boosting"
        
        pipeline = InferencePipeline(mock_config)
        pipeline.run()
        
        assert pipeline.predictions is not None
        assert len(pipeline.predictions) == 3

    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.InferencePipeline.run')
    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.RentalCostPredictor')
    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.DataLoader')
    def test_run_pipeline_function(self, mock_data_loader, mock_predictor, mock_run, mock_config):
        """Test fonction run_pipeline"""
        mock_loader_instance = MagicMock()
        mock_data_loader.return_value = mock_loader_instance
        mock_predictor_instance = MagicMock()
        mock_predictor.return_value = mock_predictor_instance
        
        run_pipeline(mock_config)
        
        mock_run.assert_called_once()

    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.RentalCostPredictor')
    @patch('soongo_data.utils.rent_cost_predict.inference_pipeline.DataLoader')
    def test_vehicle_id_preserved(self, mock_data_loader, mock_predictor, mock_config, sample_features, sample_predictions):
        """Test que les vehicle_id sont préservés dans le résultat final"""
        # Setup mocks
        mock_loader_instance = MagicMock()
        mock_data_loader.return_value = mock_loader_instance
        mock_loader_instance.load_data.return_value = sample_features
        
        mock_predictor_instance = MagicMock()
        mock_predictor.return_value = mock_predictor_instance
        mock_predictor_instance.predict.return_value = sample_predictions
        mock_predictor_instance.model_type = "hist_gradient_boosting"
        
        pipeline = InferencePipeline(mock_config)
        result = pipeline.run()
        
        # Vérifier que les vehicle_id sont les mêmes
        assert list(result['vehicle_id']) == ['v1', 'v2', 'v3']