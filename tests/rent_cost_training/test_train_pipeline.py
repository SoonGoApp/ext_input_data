"""
Tests unitaires pour train_pipeline.py
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path
from soongo_data.utils.rent_cost_training.train_pipeline import (
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
    """Données de test"""
    return pd.DataFrame({
        'vehicle_id': ['v1', 'v2', 'v3', 'v4', 'v5'],
        'brand': ['Toyota', 'Ford', 'Honda', 'Toyota', 'Ford'],
        'year': [2020, 2019, 2021, 2020, 2018],
        'mileage': [10000, 20000, 5000, 15000, 30000],
        'target': [500, 600, 550, 520, 580]
    })


def make_mock_engine(sample_data: pd.DataFrame, execute_side_effect=None):
    """Construit un mock d'engine SQLAlchemy tel qu'utilisé par
    train_pipeline.run(): `with engine.connect() as conn: conn.execute(text(...))`
    puis `pd.DataFrame(result.fetchall(), columns=result.keys())`.
    """
    mock_engine = MagicMock()
    mock_conn = MagicMock()

    if execute_side_effect is not None:
        mock_conn.execute.side_effect = execute_side_effect
    else:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = list(
            sample_data.itertuples(index=False, name=None)
        )
        mock_result.keys.return_value = list(sample_data.columns)
        mock_conn.execute.return_value = mock_result

    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_engine.connect.return_value.__exit__.return_value = False
    return mock_engine, mock_conn


class TestTrainingPipeline:
    """Tests pour TrainingPipeline"""

    @patch('soongo_data.utils.rent_cost_training.train_pipeline.gen_engine')
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
    @patch('soongo_data.utils.rent_cost_training.train_pipeline.gen_engine')
    def test_setup(self, mock_gen_engine, mock_mkdir, mock_config):
        """Test setup du pipeline"""
        mock_gen_engine.return_value = MagicMock()
        pipeline = TrainingPipeline(mock_config)

        pipeline.setup()

        # Vérifie que mkdir a été appelé
        assert mock_mkdir.called

    @patch('soongo_data.utils.rent_cost_training.train_pipeline.push_folder_to_s3')
    @patch('pathlib.Path.mkdir')
    @patch('soongo_data.utils.rent_cost_training.train_pipeline.gen_engine')
    def test_run_success(self, mock_gen_engine, mock_mkdir, mock_push_s3, mock_config, sample_data):
        """Test exécution complète du pipeline avec succès"""
        mock_engine, mock_conn = make_mock_engine(sample_data)
        mock_gen_engine.return_value = mock_engine

        pipeline = TrainingPipeline(mock_config)
        pipeline.model.train_model = MagicMock(return_value={'train_metrics': {}})
        pipeline.model.save_model = MagicMock(return_value=Path("/tmp/models/model_2024-01-01"))
        pipeline.model.remove_model_folder_from_local = MagicMock()

        # Run
        result = pipeline.run()

        # Assert
        assert result is True
        pipeline.model.train_model.assert_called_once()
        pipeline.model.save_model.assert_called_once()
        mock_push_s3.assert_called_once()
        pipeline.model.remove_model_folder_from_local.assert_called_once()
        # La requête doit bien avoir été exécutée sur la connexion
        mock_conn.execute.assert_called_once()

    @patch('pathlib.Path.mkdir')
    @patch('soongo_data.utils.rent_cost_training.train_pipeline.gen_engine')
    def test_run_with_exception(self, mock_gen_engine, mock_mkdir, mock_config):
        """Test exécution du pipeline avec exception (échec de la requête SQL)"""
        mock_engine, mock_conn = make_mock_engine(
            sample_data=None,
            execute_side_effect=Exception("Database error"),
        )
        mock_gen_engine.return_value = mock_engine

        pipeline = TrainingPipeline(mock_config)

        # Run & Assert
        with pytest.raises(Exception):
            pipeline.run()

    @patch('soongo_data.utils.rent_cost_training.train_pipeline.TrainingPipeline.run')
    @patch('soongo_data.utils.rent_cost_training.train_pipeline.gen_engine')
    def test_run_pipeline_function(self, mock_gen_engine, mock_run, mock_config):
        """Test fonction run_pipeline"""
        mock_gen_engine.return_value = MagicMock()
        mock_run.return_value = True

        run_pipeline(mock_config)

        mock_run.assert_called_once()

    @patch('soongo_data.utils.rent_cost_training.train_pipeline.push_folder_to_s3')
    @patch('pathlib.Path.mkdir')
    @patch('soongo_data.utils.rent_cost_training.train_pipeline.gen_engine')
    def test_pipeline_data_split(self, mock_gen_engine, mock_mkdir, mock_push_s3, mock_config, sample_data):
        """Test que les données sont bien séparées en features et target"""
        mock_engine, mock_conn = make_mock_engine(sample_data)
        mock_gen_engine.return_value = mock_engine

        pipeline = TrainingPipeline(mock_config)
        pipeline.model.train_model = MagicMock(return_value={'train_metrics': {}})
        pipeline.model.save_model = MagicMock(return_value=Path("/tmp/models/model_2024-01-01"))
        pipeline.model.remove_model_folder_from_local = MagicMock()

        # Run
        pipeline.run()

        # Vérifier que train_model a été appelé
        assert pipeline.model.train_model.called

        # Récupérer les arguments passés à train_model
        call_args = pipeline.model.train_model.call_args
        features = call_args[0][0]
        target = call_args[0][1]

        # Vérifier que target n'est pas dans les features
        assert 'target' not in features.columns

        # Vérifier que target contient bien la colonne target
        assert 'target' in target.columns
        assert 'vehicle_id' in target.columns

    @patch('soongo_data.utils.rent_cost_training.train_pipeline.push_folder_to_s3')
    @patch('pathlib.Path.mkdir')
    @patch('soongo_data.utils.rent_cost_training.train_pipeline.gen_engine')
    def test_query_executed_with_text_clause(self, mock_gen_engine, mock_mkdir, mock_push_s3, mock_config, sample_data):
        """Test que la requête est bien exécutée via conn.execute(text(...)),
        et pas via pd.read_sql (source du bug corrigé)."""
        mock_engine, mock_conn = make_mock_engine(sample_data)
        mock_gen_engine.return_value = mock_engine

        pipeline = TrainingPipeline(mock_config)
        pipeline.model.train_model = MagicMock(return_value={'train_metrics': {}})
        pipeline.model.save_model = MagicMock(return_value=Path("/tmp/models/model_2024-01-01"))
        pipeline.model.remove_model_folder_from_local = MagicMock()

        pipeline.run()

        # Le premier argument positionnel doit être un objet TextClause
        # (produit par sqlalchemy.text), pas une simple string.
        executed_query = mock_conn.execute.call_args[0][0]
        assert hasattr(executed_query, "text") or "TextClause" in type(executed_query).__name__