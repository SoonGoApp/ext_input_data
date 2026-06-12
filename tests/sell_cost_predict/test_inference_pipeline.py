"""
Tests unitaires pour inference_pipeline.py - Sell Cost Predict
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from soongo_data.utils.sell_cost_predict.inference_pipeline import (
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
    """Features de test alignées avec le modèle sell cost"""
    return pd.DataFrame({
        'vehicle_id':   ['v1', 'v2', 'v3'],
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
def sample_predictions():
    """Prédictions de test"""
    return np.array([25000, 32000, 28000])


class TestInferencePipeline:
    """Tests pour InferencePipeline"""

    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.SellCostPredictor')
    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.DataLoader')
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

    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.SellCostPredictor')
    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.DataLoader')
    def test_run_success(self, mock_data_loader, mock_predictor, mock_config, sample_features, sample_predictions):
        """Test exécution complète du pipeline avec succès"""
        mock_loader_instance = MagicMock()
        mock_data_loader.return_value = mock_loader_instance
        mock_loader_instance.load_data.return_value = sample_features

        mock_predictor_instance = MagicMock()
        mock_predictor.return_value = mock_predictor_instance
        mock_predictor_instance.predict.return_value = sample_predictions
        mock_predictor_instance.model_type = "hist_gradient_boosting"

        pipeline = InferencePipeline(mock_config)
        result = pipeline.run()

        assert len(result) == 3
        assert 'vehicle_id' in result.columns
        assert 'predicted_rebate_price' in result.columns
        assert 'model' in result.columns
        assert result['model'].iloc[0] == "hist_gradient_boosting"

        mock_loader_instance.load_data.assert_called_once()
        mock_predictor_instance.predict.assert_called_once()
        mock_loader_instance.write_results_to_db.assert_called_once()
        mock_predictor_instance.remove_model_folder_from_local.assert_called_once()

    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.SellCostPredictor')
    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.DataLoader')
    def test_run_prediction_failure(self, mock_data_loader, mock_predictor, mock_config, sample_features):
        """Test échec de la prédiction"""
        mock_loader_instance = MagicMock()
        mock_data_loader.return_value = mock_loader_instance
        mock_loader_instance.load_data.return_value = sample_features

        mock_predictor_instance = MagicMock()
        mock_predictor.return_value = mock_predictor_instance
        mock_predictor_instance.predict.side_effect = Exception("Prediction error")

        pipeline = InferencePipeline(mock_config)

        with pytest.raises(Exception):
            pipeline.run()

    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.SellCostPredictor')
    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.DataLoader')
    def test_run_data_loading_failure(self, mock_data_loader, mock_predictor, mock_config):
        """Test échec du chargement des données"""
        mock_loader_instance = MagicMock()
        mock_data_loader.return_value = mock_loader_instance
        mock_loader_instance.load_data.side_effect = Exception("Data loading error")

        mock_predictor_instance = MagicMock()
        mock_predictor.return_value = mock_predictor_instance

        pipeline = InferencePipeline(mock_config)

        with pytest.raises(Exception):
            pipeline.run()

    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.SellCostPredictor')
    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.DataLoader')
    def test_run_write_failure(self, mock_data_loader, mock_predictor, mock_config, sample_features, sample_predictions):
        """Test échec de l'écriture en DB"""
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

    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.SellCostPredictor')
    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.DataLoader')
    def test_predictions_stored(self, mock_data_loader, mock_predictor, mock_config, sample_features, sample_predictions):
        """Test que les prédictions sont stockées dans l'instance"""
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

    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.InferencePipeline.run')
    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.SellCostPredictor')
    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.DataLoader')
    def test_run_pipeline_function(self, mock_data_loader, mock_predictor, mock_run, mock_config):
        """Test fonction run_pipeline"""
        mock_data_loader.return_value = MagicMock()
        mock_predictor.return_value = MagicMock()

        run_pipeline(mock_config)

        mock_run.assert_called_once()

    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.SellCostPredictor')
    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.DataLoader')
    def test_vehicle_id_preserved(self, mock_data_loader, mock_predictor, mock_config, sample_features, sample_predictions):
        """Test que les vehicle_id sont préservés dans le résultat final"""
        mock_loader_instance = MagicMock()
        mock_data_loader.return_value = mock_loader_instance
        mock_loader_instance.load_data.return_value = sample_features

        mock_predictor_instance = MagicMock()
        mock_predictor.return_value = mock_predictor_instance
        mock_predictor_instance.predict.return_value = sample_predictions
        mock_predictor_instance.model_type = "hist_gradient_boosting"

        pipeline = InferencePipeline(mock_config)
        result = pipeline.run()

        assert list(result['vehicle_id']) == ['v1', 'v2', 'v3']

    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.SellCostPredictor')
    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.DataLoader')
    def test_final_df_columns_only(self, mock_data_loader, mock_predictor, mock_config, sample_features, sample_predictions):
        """Test que le dataframe final contient uniquement les colonnes attendues"""
        mock_loader_instance = MagicMock()
        mock_data_loader.return_value = mock_loader_instance
        mock_loader_instance.load_data.return_value = sample_features

        mock_predictor_instance = MagicMock()
        mock_predictor.return_value = mock_predictor_instance
        mock_predictor_instance.predict.return_value = sample_predictions
        mock_predictor_instance.model_type = "hist_gradient_boosting"

        pipeline = InferencePipeline(mock_config)
        result = pipeline.run()

        assert set(result.columns) == {'vehicle_id', 'predicted_rebate_price', 'model'}

    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.SellCostPredictor')
    @patch('soongo_data.utils.sell_cost_predict.inference_pipeline.DataLoader')
    def test_predict_called_without_vehicle_id(self, mock_data_loader, mock_predictor, mock_config, sample_features, sample_predictions):
        """Test que predict est appelé sans la colonne vehicle_id"""
        mock_loader_instance = MagicMock()
        mock_data_loader.return_value = mock_loader_instance
        mock_loader_instance.load_data.return_value = sample_features

        mock_predictor_instance = MagicMock()
        mock_predictor.return_value = mock_predictor_instance
        mock_predictor_instance.predict.return_value = sample_predictions
        mock_predictor_instance.model_type = "hist_gradient_boosting"

        pipeline = InferencePipeline(mock_config)
        pipeline.run()

        call_args = mock_predictor_instance.predict.call_args
        features_passed = call_args[0][0]
        assert 'vehicle_id' not in features_passed.columns