import pytest
from unittest.mock import MagicMock, patch, mock_open
import importlib


# ── helpers ───────────────────────────────────────────────────────────────────

FAKE_CONFIG = {"bucket_name": "test-bucket", "model_folder": "models"}
FAKE_DB_INFO = {"DATABASE_URL": "postgresql://user:pass@localhost/db"}


def get_handler():
    import soongo_data.utils.eligibility_electrif_predict as pkg
    import infrastructure.lambdas.electrification_eligibility_ml_prediction.app as app_module
    importlib.reload(app_module)
    return app_module.lambda_handler


@pytest.fixture(autouse=True)
def mock_deps():
    with patch("soongo_data.utils.eligibility_electrif_predict.run_pipeline") as mock_run, \
         patch("soongo_data.utils.logging_utils.gen_logger", return_value=MagicMock()), \
         patch("soongo_data.utils.secrets_utils.get_local_secret", return_value=FAKE_DB_INFO), \
         patch("soongo_data.utils.aws.send_ses_email") as mock_email, \
         patch("builtins.open", mock_open(read_data="bucket_name: test-bucket")), \
         patch("yaml.safe_load", return_value=FAKE_CONFIG):
        yield {"run_pipeline": mock_run, "send_ses_email": mock_email}


# ── happy path ────────────────────────────────────────────────────────────────

def test_returns_success_status(mock_deps):
    handler = get_handler()
    result = handler(context=None)
    assert result == {"status": "success"}

def test_run_pipeline_called(mock_deps):
    handler = get_handler()
    handler(context=None)
    mock_deps["run_pipeline"].assert_called_once()

def test_run_pipeline_called_with_config(mock_deps):
    handler = get_handler()
    handler(context=None)
    call_kwargs = mock_deps["run_pipeline"].call_args
    assert call_kwargs is not None

def test_no_email_on_success(mock_deps):
    handler = get_handler()
    handler(context=None)
    mock_deps["send_ses_email"].assert_not_called()


# ── error path ────────────────────────────────────────────────────────────────

def test_email_sent_on_error(mock_deps):
    mock_deps["run_pipeline"].side_effect = RuntimeError("pipeline failed")
    handler = get_handler()
    handler(context=None)
    mock_deps["send_ses_email"].assert_called_once()

def test_no_reraise_on_error(mock_deps):
    mock_deps["run_pipeline"].side_effect = RuntimeError("pipeline failed")
    handler = get_handler()
    handler(context=None)  # ne doit pas lever d'exception

def test_email_recipient(mock_deps):
    mock_deps["run_pipeline"].side_effect = RuntimeError("oops")
    handler = get_handler()
    handler(context=None)
    _, kwargs = mock_deps["send_ses_email"].call_args
    assert kwargs.get("recipient_email") == "data@soongo.co"

def test_email_sender(mock_deps):
    mock_deps["run_pipeline"].side_effect = RuntimeError("oops")
    handler = get_handler()
    handler(context=None)
    _, kwargs = mock_deps["send_ses_email"].call_args
    assert kwargs.get("sender_email") == "infra@soongo.co"

def test_email_subject_contains_alert(mock_deps):
    mock_deps["run_pipeline"].side_effect = RuntimeError("oops")
    handler = get_handler()
    handler(context=None)
    _, kwargs = mock_deps["send_ses_email"].call_args
    assert "Alert" in kwargs.get("subject", "")

def test_handles_file_not_found(mock_deps):
    with patch("builtins.open", side_effect=FileNotFoundError("no config")):
        handler = get_handler()
        handler(context=None)  # ne doit pas lever d'exception
    mock_deps["send_ses_email"].assert_called_once()