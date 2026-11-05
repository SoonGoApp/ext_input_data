# ===================== test_inference_pipeline.py =====================
"""
Tests unitaires pour inference_pipeline.py (rent)
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

from soongo_data.utils.rent_cost_predict.inference_pipeline import (
    InferencePipeline,
    run_pipeline,
)

MODULE = 'soongo_data.utils.rent_cost_predict.inference_pipeline'


@pytest.fixture
def mock_config():
    return {"bucket_name": "test-bucket", "model_folder": "models", "models_dir": "/tmp/models"}


@pytest.fixture
def sample_features():
    return pd.DataFrame({
        'vehicle_id': ['v1', 'v2', 'v3'],
        'brand': ['Toyota', 'Ford', 'Honda'],
        'year': [2020, 2019, 2021],
        'mileage': [10000, 20000, 5000],
    })


@pytest.fixture
def sample_predictions():
    return np.array([500.0, 600.0, 550.0])


@pytest.fixture
def mocks(sample_features, sample_predictions):
    """Patch DataLoader et RentalCostPredictor ; retourne (loader, predictor)."""
    with patch(f'{MODULE}.DataLoader') as loader_cls, \
            patch(f'{MODULE}.RentalCostPredictor') as predictor_cls:
        loader = loader_cls.return_value
        loader.load_data.return_value = sample_features
        predictor = predictor_cls.return_value
        predictor.predict.return_value = sample_predictions
        predictor.model_type = "hist_gradient_boosting"
        yield loader, predictor, loader_cls, predictor_cls


class TestInit:

    def test_init(self, mocks, mock_config):
        loader, predictor, loader_cls, predictor_cls = mocks

        pipeline = InferencePipeline(mock_config)

        assert pipeline.config == mock_config
        assert pipeline.data_loader is loader
        assert pipeline.model is predictor
        assert pipeline.predictions is None
        loader_cls.assert_called_once_with(config=mock_config)
        predictor_cls.assert_called_once_with(config=mock_config)


class TestRun:

    def test_run_success(self, mocks, mock_config):
        loader, predictor, _, _ = mocks

        result = InferencePipeline(mock_config).run()

        assert len(result) == 3
        assert list(result['model']) == ["hist_gradient_boosting"] * 3
        loader.load_data.assert_called_once()
        predictor.predict.assert_called_once()
        loader.write_results_to_db.assert_called_once()
        predictor.remove_model_folder_from_local.assert_called_once()

    def test_output_columns_exact(self, mocks, mock_config):
        result = InferencePipeline(mock_config).run()
        assert list(result.columns) == ['vehicle_id', 'predicted_total_rent_tax_exc', 'model']

    def test_vehicle_id_preserved(self, mocks, mock_config):
        result = InferencePipeline(mock_config).run()
        assert list(result['vehicle_id']) == ['v1', 'v2', 'v3']

    def test_predictions_aligned_with_vehicles(self, mocks, mock_config):
        result = InferencePipeline(mock_config).run()
        assert list(result['predicted_total_rent_tax_exc']) == [500.0, 600.0, 550.0]

    def test_predict_receives_features_without_vehicle_id(self, mocks, mock_config):
        _, predictor, _, _ = mocks

        InferencePipeline(mock_config).run()

        X = predictor.predict.call_args[0][0]
        assert 'vehicle_id' not in X.columns
        assert list(X.columns) == ['brand', 'year', 'mileage']

    def test_predictions_stored(self, mocks, mock_config):
        pipeline = InferencePipeline(mock_config)
        pipeline.run()
        assert len(pipeline.predictions) == 3

    def test_model_type_written_in_model_column(self, mocks, mock_config):
        _, predictor, _, _ = mocks
        predictor.model_type = "blend"

        result = InferencePipeline(mock_config).run()

        assert set(result['model']) == {"blend"}

    def test_write_receives_final_df(self, mocks, mock_config):
        loader, _, _, _ = mocks

        result = InferencePipeline(mock_config).run()

        written = loader.write_results_to_db.call_args[0][0]
        assert written is result

    def test_order_load_predict_write_cleanup(self, mocks, mock_config, sample_features, sample_predictions):
        loader, predictor, _, _ = mocks
        calls = []
        loader.load_data.side_effect = lambda: calls.append("load") or sample_features
        predictor.predict.side_effect = lambda X: calls.append("predict") or sample_predictions
        loader.write_results_to_db.side_effect = lambda df: calls.append("write")
        predictor.remove_model_folder_from_local.side_effect = lambda: calls.append("cleanup")

        InferencePipeline(mock_config).run()

        assert calls == ["load", "predict", "write", "cleanup"]

    # ---- échecs ----

    def test_data_loading_failure(self, mocks, mock_config):
        loader, predictor, _, _ = mocks
        loader.load_data.side_effect = Exception("Data loading error")

        with pytest.raises(Exception, match="Data loading error"):
            InferencePipeline(mock_config).run()

        predictor.predict.assert_not_called()
        loader.write_results_to_db.assert_not_called()

    def test_prediction_failure_no_write(self, mocks, mock_config):
        loader, predictor, _, _ = mocks
        predictor.predict.side_effect = Exception("Prediction error")

        with pytest.raises(Exception, match="Prediction error"):
            InferencePipeline(mock_config).run()

        loader.write_results_to_db.assert_not_called()
        predictor.remove_model_folder_from_local.assert_not_called()

    def test_write_failure_keeps_model_folder(self, mocks, mock_config):
        loader, predictor, _, _ = mocks
        loader.write_results_to_db.side_effect = Exception("Write error")

        with pytest.raises(Exception, match="Write error"):
            InferencePipeline(mock_config).run()

        predictor.remove_model_folder_from_local.assert_not_called()

    def test_failure_is_logged(self, mocks, mock_config):
        _, predictor, _, _ = mocks
        predictor.predict.side_effect = RuntimeError("boom")

        with patch(f'{MODULE}.logger') as log, pytest.raises(RuntimeError):
            InferencePipeline(mock_config).run()

        log.error.assert_called_once()
        assert "boom" in log.error.call_args[0][0]


class TestRunPipeline:

    def test_run_pipeline_builds_and_runs(self, mock_config):
        with patch(f'{MODULE}.InferencePipeline') as cls:
            run_pipeline(mock_config)
        cls.assert_called_once_with(config=mock_config)
        cls.return_value.run.assert_called_once()

    def test_run_pipeline_propagates_errors(self, mock_config):
        with patch(f'{MODULE}.InferencePipeline') as cls:
            cls.return_value.run.side_effect = RuntimeError("fail")
            with pytest.raises(RuntimeError, match="fail"):
                run_pipeline(mock_config)

    def test_run_pipeline_end_to_end_mocked_deps(self, mocks, mock_config):
        loader, _, _, _ = mocks
        run_pipeline(mock_config)
        loader.write_results_to_db.assert_called_once()