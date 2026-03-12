import pytest
from unittest.mock import MagicMock, patch, mock_open


# ── config mockée ───

MOCK_CONFIG = {
    "model_type": "random_forest",
    "models_dir": "/tmp/models",
    "bucket_name": "test-bucket",
}


@pytest.fixture(autouse=True)
def mock_all_deps():
    """Mocke toutes les dépendances externes avant chaque test."""
    with patch("soongo_data.utils.eligibility_electrif_training.run_pipeline") as mock_run, \
         patch("soongo_data.utils.logging_utils.gen_logger", return_value=MagicMock()) as mock_logger, \
         patch("soongo_data.utils.secrets_utils.get_local_secret", return_value={"DATABASE_URL": "postgresql://test"}), \
         patch("soongo_data.utils.aws.send_ses_email") as mock_email, \
         patch("builtins.open", mock_open(read_data="model_type: random_forest\n")), \
         patch("yaml.safe_load", return_value=MOCK_CONFIG):
        yield {
            "run_pipeline": mock_run,
            "send_email":   mock_email,
            "logger":       mock_logger,
        }


def get_handler():
    """Importe lambda_handler après que les mocks sont en place."""
    import importlib
    import infrastructure.lambdas.electrification_eligibility_ml_training.app as app
    importlib.reload(app)
    return app.lambda_handler


# ── happy path ───

def test_returns_success_status(mock_all_deps):
    handler = get_handler()
    result = handler(context=None)
    assert result == {"status": "success"}

def test_run_pipeline_called(mock_all_deps):
    handler = get_handler()
    handler(context=None)
    mock_all_deps["run_pipeline"].assert_called_once()

def test_run_pipeline_called_with_config(mock_all_deps):
    handler = get_handler()
    handler(context=None)
    call_kwargs = mock_all_deps["run_pipeline"].call_args.kwargs
    assert call_kwargs["config"] == MOCK_CONFIG

def test_no_email_sent_on_success(mock_all_deps):
    handler = get_handler()
    handler(context=None)
    mock_all_deps["send_email"].assert_not_called()


# ── error handling ───

def test_sends_email_on_error(mock_all_deps):
    mock_all_deps["run_pipeline"].side_effect = RuntimeError("Pipeline failed")
    handler = get_handler()
    handler(context=None)
    mock_all_deps["send_email"].assert_called_once()

def test_does_not_reraise_exception(mock_all_deps):
    mock_all_deps["run_pipeline"].side_effect = RuntimeError("Pipeline failed")
    handler = get_handler()
    handler(context=None)  # ne doit pas lever d'exception

def test_email_sent_to_data_team(mock_all_deps):
    mock_all_deps["run_pipeline"].side_effect = RuntimeError("err")
    handler = get_handler()
    handler(context=None)
    call_kwargs = mock_all_deps["send_email"].call_args.kwargs
    assert call_kwargs["recipient_email"] == "data@soongo.co"

def test_email_sent_from_infra(mock_all_deps):
    mock_all_deps["run_pipeline"].side_effect = RuntimeError("err")
    handler = get_handler()
    handler(context=None)
    call_kwargs = mock_all_deps["send_email"].call_args.kwargs
    assert call_kwargs["sender_email"] == "infra@soongo.co"

def test_email_subject_contains_alert(mock_all_deps):
    mock_all_deps["run_pipeline"].side_effect = RuntimeError("err")
    handler = get_handler()
    handler(context=None)
    call_kwargs = mock_all_deps["send_email"].call_args.kwargs
    assert "Alert" in call_kwargs["subject"]

def test_handles_missing_config_file(mock_all_deps):
    with patch("builtins.open", side_effect=FileNotFoundError("no file")):
        handler = get_handler()
        handler(context=None)  # ne doit pas lever d'exception
    mock_all_deps["send_email"].assert_called_once()