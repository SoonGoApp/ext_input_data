"""
Tests unitaires pour train_pipeline.py - Sell Cost (Rebate Price)
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path
from soongo_data.utils.sell_cost_training.train_pipeline import (
    TrainingPipeline,
    run_pipeline
)


@pytest.fixture
def mock_config():
    """Configuration de test"""
    return {
        "models_dir": "/tmp/models",
        "bucket_name": "test-bucket",
        "model_type": "hist_gradient_boosting",
        "test_size": 0.3,
        "random_state": 42,
        "model_params": {}
    }


@pytest.fixture
def sample_data():
    """Données de test alignées avec les features du modèle sell cost"""
    return pd.DataFrame({
        'vehicle_id':   ['v1', 'v2', 'v3', 'v4', 'v5'],
        'brand':        ['Toyota', 'Ford', 'Honda', 'Toyota', 'Ford'],
        'entry_year':   [2020, 2019, 2021, 2020, 2018],
        'age':          [6, 7, 5, 6, 8],
        'segment':      ['SUV', 'Berline', 'SUV', 'Berline', 'SUV'],
        'energy':       ['Diesel', 'Petrol', 'Electric', 'Diesel', 'Petrol'],
        'fiscal_power': [6.0, 7.0, 5.0, 6.0, 8.0],
        'seat_count':   [5.0, 5.0, 5.0, 7.0, 5.0],
        'transmission': ['Manual', 'Auto', 'Auto', 'Manual', 'Auto'],
        'motor_power':  [110.0, 130.0, 150.0, 110.0, 90.0],
        'target':       [25000, 32000, 28000, 26000, 30000]
    })


class TestTrainingPipeline:
    """Tests pour TrainingPipeline"""

    @patch('soongo_data.utils.sell_cost_training.train_pipeline.gen_engine')
    def test_init(self, mock_gen_engine, mock_config):
        """Test initialisation du pipeline"""
        mock_engine = MagicMock()
        mock_gen_engine.return_value = mock_engine

        pipeline = TrainingPipeline(mock_config)

        assert pipeline.config == mock_config
        assert pipeline.engine == mock_engine
        assert pipeline.model is not None
        assert pipeline.results == {}

    @patch('pathlib.Path.mkdir')
    @patch('soongo_data.utils.sell_cost_training.train_pipeline.gen_engine')
    def test_setup(self, mock_gen_engine, mock_mkdir, mock_config):
        """Test setup du pipeline"""
        mock_gen_engine.return_value = MagicMock()
        pipeline = TrainingPipeline(mock_config)

        pipeline.setup()

        assert mock_mkdir.called

    @patch('soongo_data.utils.sell_cost_training.train_pipeline.push_folder_to_s3')
    @patch('soongo_data.utils.sell_cost_training.train_pipeline.pd.read_sql')
    @patch('pathlib.Path.mkdir')
    @patch('soongo_data.utils.sell_cost_training.train_pipeline.gen_engine')
    def test_run_success(self, mock_gen_engine, mock_mkdir, mock_read_sql, mock_push_s3, mock_config, sample_data):
        """Test exécution complète du pipeline avec succès"""
        mock_gen_engine.return_value = MagicMock()
        mock_read_sql.return_value = sample_data

        pipeline = TrainingPipeline(mock_config)
        pipeline.model.train_model = MagicMock(return_value={'train_metrics': {}})
        pipeline.model.save_model = MagicMock(return_value=Path("/tmp/models/model_2024-01-01"))
        pipeline.model.remove_model_folder_from_local = MagicMock()

        result = pipeline.run()

        assert result is True
        pipeline.model.train_model.assert_called_once()
        pipeline.model.save_model.assert_called_once()
        mock_push_s3.assert_called_once()

    @patch('soongo_data.utils.sell_cost_training.train_pipeline.pd.read_sql')
    @patch('pathlib.Path.mkdir')
    @patch('soongo_data.utils.sell_cost_training.train_pipeline.gen_engine')
    def test_run_with_exception(self, mock_gen_engine, mock_mkdir, mock_read_sql, mock_config):
        """Test exécution du pipeline avec exception"""
        mock_gen_engine.return_value = MagicMock()
        mock_read_sql.side_effect = Exception("Database error")

        pipeline = TrainingPipeline(mock_config)

        with pytest.raises(Exception):
            pipeline.run()

    @patch('soongo_data.utils.sell_cost_training.train_pipeline.TrainingPipeline.run')
    @patch('soongo_data.utils.sell_cost_training.train_pipeline.gen_engine')
    def test_run_pipeline_function(self, mock_gen_engine, mock_run, mock_config):
        """Test fonction run_pipeline"""
        mock_gen_engine.return_value = MagicMock()
        mock_run.return_value = True

        run_pipeline(mock_config)

        mock_run.assert_called_once()

    @patch('soongo_data.utils.sell_cost_training.train_pipeline.push_folder_to_s3')
    @patch('soongo_data.utils.sell_cost_training.train_pipeline.pd.read_sql')
    @patch('pathlib.Path.mkdir')
    @patch('soongo_data.utils.sell_cost_training.train_pipeline.gen_engine')
    def test_pipeline_data_split(self, mock_gen_engine, mock_mkdir, mock_read_sql, mock_push_s3, mock_config, sample_data):
        """Test que les données sont bien séparées en features et target"""
        mock_gen_engine.return_value = MagicMock()
        mock_read_sql.return_value = sample_data

        pipeline = TrainingPipeline(mock_config)
        pipeline.model.train_model = MagicMock(return_value={'train_metrics': {}})
        pipeline.model.save_model = MagicMock(return_value=Path("/tmp/models/model_2024-01-01"))
        pipeline.model.remove_model_folder_from_local = MagicMock()

        pipeline.run()

        assert pipeline.model.train_model.called

        call_args = pipeline.model.train_model.call_args
        features = call_args[0][0]
        target = call_args[0][1]

        # target ne doit pas être dans les features
        assert 'target' not in features.columns

        # target doit contenir la colonne target
        assert 'target' in target.columns

    @patch('soongo_data.utils.sell_cost_training.train_pipeline.push_folder_to_s3')
    @patch('soongo_data.utils.sell_cost_training.train_pipeline.pd.read_sql')
    @patch('pathlib.Path.mkdir')
    @patch('soongo_data.utils.sell_cost_training.train_pipeline.gen_engine')
    def test_pipeline_vehicle_id_in_target(self, mock_gen_engine, mock_mkdir, mock_read_sql, mock_push_s3, mock_config, sample_data):
        """Test que vehicle_id est bien présent dans le target"""
        mock_gen_engine.return_value = MagicMock()
        mock_read_sql.return_value = sample_data

        pipeline = TrainingPipeline(mock_config)
        pipeline.model.train_model = MagicMock(return_value={'train_metrics': {}})
        pipeline.model.save_model = MagicMock(return_value=Path("/tmp/models/model_2024-01-01"))

        pipeline.run()

        call_args = pipeline.model.train_model.call_args
        target = call_args[0][1]

        assert 'vehicle_id' in target.columns