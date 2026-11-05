"""
Tests unitaires pour train_pipeline.py
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path

from soongo_data.utils.rent_cost_training.train_pipeline import (
    TrainingPipeline,
    run_pipeline,
)

MODULE = 'soongo_data.utils.rent_cost_training.train_pipeline'


@pytest.fixture
def mock_config(tmp_path):
    return {
        "models_dir": str(tmp_path / "models"),
        "bucket_name": "test-bucket",
        "model_type": "hist_gradient_boosting",
        "test_size": 0.3,
        "random_state": 42,
        "model_params": {},
    }


@pytest.fixture
def sample_data():
    return pd.DataFrame({
        'vehicle_id': ['v1', 'v2', 'v3', 'v4', 'v5'],
        'brand': ['Toyota', 'Ford', 'Honda', 'Toyota', 'Ford'],
        'model': ['Yaris', 'Fiesta', 'Civic', 'Corolla', 'Focus'],
        'year': [2020, 2019, 2021, 2020, 2018],
        'mileage': [10000, 20000, 5000, 15000, 30000],
        'target': [500, 600, 550, 520, 580],
    })


def make_mock_engine(sample_data, execute_side_effect=None):
    """Mock d'engine SQLAlchemy : `with engine.connect() as conn:
    conn.execute(text(...))` puis DataFrame(result.fetchall(), columns=result.keys())."""
    engine = MagicMock()
    conn = MagicMock()

    if execute_side_effect is not None:
        conn.execute.side_effect = execute_side_effect
    else:
        result = MagicMock()
        result.fetchall.return_value = list(sample_data.itertuples(index=False, name=None))
        result.keys.return_value = list(sample_data.columns)
        conn.execute.return_value = result

    engine.connect.return_value.__enter__.return_value = conn
    engine.connect.return_value.__exit__.return_value = False
    return engine, conn


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")


@pytest.fixture
def pipeline_factory(mock_config, sample_data, env):
    """Construit un pipeline avec engine, BCE, S3 et modèle mockés."""
    def build(data=None, execute_side_effect=None):
        data = sample_data if data is None else data
        engine, conn = make_mock_engine(data, execute_side_effect)
        with patch(f'{MODULE}.gen_engine', return_value=engine) as gen:
            pipeline = TrainingPipeline(mock_config)
        pipeline.model.train_model = MagicMock(return_value={'train_metrics': {}})
        pipeline.model.save_model = MagicMock(return_value=Path("models/model_2024-01-01"))
        pipeline.model.remove_model_folder_from_local = MagicMock()
        pipeline._conn, pipeline._gen = conn, gen
        return pipeline
    return build


class TestInit:

    @patch(f'{MODULE}.gen_engine')
    def test_init(self, mock_gen_engine, mock_config, env):
        engine = MagicMock()
        mock_gen_engine.return_value = engine

        pipeline = TrainingPipeline(mock_config)

        assert pipeline.config == mock_config
        assert pipeline.engine is engine
        assert pipeline.model is not None
        assert pipeline.model.config == mock_config
        assert pipeline.results == {}

    @patch(f'{MODULE}.gen_engine')
    def test_init_uses_database_url_env(self, mock_gen_engine, mock_config, env):
        TrainingPipeline(mock_config)
        mock_gen_engine.assert_called_once_with(database_url="postgresql://user:pw@host/db")

    @patch(f'{MODULE}.gen_engine')
    def test_init_without_database_url_raises(self, mock_gen_engine, mock_config, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(KeyError):
            TrainingPipeline(mock_config)


class TestSetup:

    @patch(f'{MODULE}.gen_engine')
    def test_setup_creates_models_dir(self, mock_gen_engine, mock_config, env):
        pipeline = TrainingPipeline(mock_config)

        pipeline.setup()

        assert Path(mock_config["models_dir"]).is_dir()

    @patch(f'{MODULE}.gen_engine')
    def test_setup_is_idempotent(self, mock_gen_engine, mock_config, env):
        pipeline = TrainingPipeline(mock_config)
        pipeline.setup()
        pipeline.setup()
        assert Path(mock_config["models_dir"]).is_dir()


@patch(f'{MODULE}.push_folder_to_s3')
@patch(f'{MODULE}.add_ecb_features', side_effect=lambda df: df)
class TestRun:

    def test_run_success(self, mock_ecb, mock_push, pipeline_factory, mock_config):
        pipeline = pipeline_factory()

        assert pipeline.run() is True

        pipeline.model.train_model.assert_called_once()
        pipeline.model.save_model.assert_called_once()
        mock_push.assert_called_once()
        pipeline.model.remove_model_folder_from_local.assert_called_once()
        pipeline._conn.execute.assert_called_once()

    def test_results_stored(self, mock_ecb, mock_push, pipeline_factory):
        pipeline = pipeline_factory()
        pipeline.model.train_model.return_value = {'train_metrics': {'cv_r2_mean': 0.7}}

        pipeline.run()

        assert pipeline.results == {'train_metrics': {'cv_r2_mean': 0.7}}

    def test_save_model_receives_results_and_config(self, mock_ecb, mock_push, pipeline_factory, mock_config):
        pipeline = pipeline_factory()
        pipeline.model.train_model.return_value = {'k': 1}

        pipeline.run()

        pipeline.model.save_model.assert_called_once_with({'k': 1}, mock_config)

    def test_data_split_features_and_target(self, mock_ecb, mock_push, pipeline_factory, sample_data):
        pipeline = pipeline_factory()

        pipeline.run()

        features, target = pipeline.model.train_model.call_args[0]
        assert 'target' not in features.columns
        assert 'vehicle_id' in features.columns
        assert list(target.columns) == ['vehicle_id', 'target']
        assert list(target['target']) == list(sample_data['target'])
        assert len(features) == len(target) == len(sample_data)

    def test_query_executed_with_text_clause(self, mock_ecb, mock_push, pipeline_factory):
        from soongo_data.utils.rent_cost_training.sql_requests import SELECT_ALL_FEATURES_TRAINING
        pipeline = pipeline_factory()

        pipeline.run()

        query = pipeline._conn.execute.call_args[0][0]
        assert "TextClause" in type(query).__name__
        assert str(query) == SELECT_ALL_FEATURES_TRAINING

    def test_ecb_features_added_before_split(self, mock_ecb, mock_push, pipeline_factory):
        enriched = lambda df: df.assign(ecb_rate=2.0, interest_per_month=10.0)
        mock_ecb.side_effect = enriched
        pipeline = pipeline_factory()

        pipeline.run()

        mock_ecb.assert_called_once()
        features, target = pipeline.model.train_model.call_args[0]
        assert {'ecb_rate', 'interest_per_month'} <= set(features.columns)
        assert 'ecb_rate' not in target.columns

    def test_s3_upload_args(self, mock_ecb, mock_push, pipeline_factory):
        pipeline = pipeline_factory()
        model_dir = Path("models/model_2024-01-01")
        pipeline.model.save_model.return_value = model_dir

        pipeline.run()

        mock_push.assert_called_once_with(
            local_dir=model_dir,
            s3_prefix=str(model_dir),
            bucket_name="test-bucket",
        )

    def test_order_train_save_push_cleanup(self, mock_ecb, mock_push, pipeline_factory):
        pipeline = pipeline_factory()
        calls = []
        pipeline.model.train_model.side_effect = lambda *a: calls.append("train") or {}
        pipeline.model.save_model.side_effect = lambda *a: calls.append("save") or Path("m")
        mock_push.side_effect = lambda **k: calls.append("push")
        pipeline.model.remove_model_folder_from_local.side_effect = lambda: calls.append("cleanup")

        pipeline.run()

        assert calls == ["train", "save", "push", "cleanup"]

    def test_creates_models_dir(self, mock_ecb, mock_push, pipeline_factory, mock_config):
        pipeline = pipeline_factory()
        pipeline.run()
        assert Path(mock_config["models_dir"]).is_dir()

    # ---- échecs ----

    def test_sql_failure_propagates_and_stops(self, mock_ecb, mock_push, pipeline_factory):
        pipeline = pipeline_factory(execute_side_effect=Exception("Database error"))

        with pytest.raises(Exception, match="Database error"):
            pipeline.run()

        pipeline.model.train_model.assert_not_called()
        mock_push.assert_not_called()

    def test_ecb_failure_propagates(self, mock_ecb, mock_push, pipeline_factory):
        mock_ecb.side_effect = RuntimeError("ECB down")
        pipeline = pipeline_factory()

        with pytest.raises(RuntimeError, match="ECB down"):
            pipeline.run()

        pipeline.model.train_model.assert_not_called()

    def test_training_failure_no_save_no_upload(self, mock_ecb, mock_push, pipeline_factory):
        pipeline = pipeline_factory()
        pipeline.model.train_model.side_effect = ValueError("Pas assez de groupes")

        with pytest.raises(ValueError, match="Pas assez de groupes"):
            pipeline.run()

        pipeline.model.save_model.assert_not_called()
        mock_push.assert_not_called()
        pipeline.model.remove_model_folder_from_local.assert_not_called()

    def test_upload_failure_keeps_local_folder(self, mock_ecb, mock_push, pipeline_factory):
        mock_push.side_effect = Exception("S3 error")
        pipeline = pipeline_factory()

        with pytest.raises(Exception, match="S3 error"):
            pipeline.run()

        pipeline.model.remove_model_folder_from_local.assert_not_called()

    def test_failure_is_logged(self, mock_ecb, mock_push, pipeline_factory):
        pipeline = pipeline_factory()
        pipeline.model.train_model.side_effect = RuntimeError("boom")

        with patch(f'{MODULE}.logger') as log, pytest.raises(RuntimeError):
            pipeline.run()

        log.error.assert_called_once()
        assert "boom" in log.error.call_args[0][0]


class TestRunPipeline:

    @patch(f'{MODULE}.TrainingPipeline')
    def test_run_pipeline_builds_and_runs(self, mock_cls, mock_config):
        run_pipeline(mock_config)

        mock_cls.assert_called_once_with(config=mock_config)
        mock_cls.return_value.run.assert_called_once()

    @patch(f'{MODULE}.TrainingPipeline.run', return_value=True)
    @patch(f'{MODULE}.gen_engine')
    def test_run_pipeline_function(self, mock_gen_engine, mock_run, mock_config, env):
        run_pipeline(mock_config)
        mock_run.assert_called_once()

    @patch(f'{MODULE}.TrainingPipeline')
    def test_run_pipeline_propagates_errors(self, mock_cls, mock_config):
        mock_cls.return_value.run.side_effect = RuntimeError("fail")
        with pytest.raises(RuntimeError, match="fail"):
            run_pipeline(mock_config)