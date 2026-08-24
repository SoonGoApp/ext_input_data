"""
Tests unitaires pour app.py - Sell Cost (Rebate Price) ML Training
"""

import pytest
from unittest.mock import MagicMock, patch, mock_open


# ── helpers ───────────────────────────────────────────────────────────────────

FAKE_CONFIG = {"bucket_name": "test-bucket", "models_dir": "/tmp/models"}
FAKE_DB_INFO = {"DATABASE_URL": "postgresql://user:pass@localhost/db"}


# ── Mock AVANT les imports ───────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_all_deps():
    """Mock TOUTES les dépendances AVANT import"""
    with patch("infrastructure.lambdas.sell_cost_ml_training.app.run_pipeline") as mock_run, \
         patch("infrastructure.lambdas.sell_cost_ml_training.app.gen_logger") as mock_logger, \
         patch("infrastructure.lambdas.sell_cost_ml_training.app.get_local_secret") as mock_secret, \
         patch("infrastructure.lambdas.sell_cost_ml_training.app.send_ses_email") as mock_email, \
         patch("builtins.open", mock_open(read_data="bucket_name: test-bucket\nmodels_dir: /tmp/models")), \
         patch("yaml.safe_load", return_value=FAKE_CONFIG):

        mock_logger.return_value = MagicMock()
        mock_secret.return_value = FAKE_DB_INFO

        yield {
            "run_pipeline": mock_run,
            "send_ses_email": mock_email,
            "gen_logger": mock_logger,
            "get_local_secret": mock_secret
        }


def get_handler():
    """Import et retourne le lambda_handler"""
    import infrastructure.lambdas.sell_cost_ml_training.app as app_module
    return app_module.lambda_handler


# ── happy path ────────────────────────────────────────────────────────────────

def test_returns_success_status(mock_all_deps):
    """Test retourne status success"""
    handler = get_handler()
    result = handler(context=None)
    assert result == {"status": "success"}


def test_run_pipeline_called(mock_all_deps):
    """Test que run_pipeline est appelé"""
    handler = get_handler()
    handler(context=None)
    mock_all_deps["run_pipeline"].assert_called_once()


def test_run_pipeline_called_with_config(mock_all_deps):
    """Test que run_pipeline reçoit une config"""
    handler = get_handler()
    handler(context=None)
    call_kwargs = mock_all_deps["run_pipeline"].call_args
    assert call_kwargs is not None
    assert "config" in call_kwargs[1]


def test_no_email_on_success(mock_all_deps):
    """Test qu'aucun email n'est envoyé en cas de succès"""
    handler = get_handler()
    handler(context=None)
    mock_all_deps["send_ses_email"].assert_not_called()


# ── error path ────────────────────────────────────────────────────────────────

def test_email_sent_on_error(mock_all_deps):
    """Test qu'un email est envoyé en cas d'erreur"""
    mock_all_deps["run_pipeline"].side_effect = RuntimeError("pipeline failed")
    handler = get_handler()
    handler(context=None)
    mock_all_deps["send_ses_email"].assert_called_once()


def test_no_reraise_on_error(mock_all_deps):
    """Test que l'erreur n'est pas re-levée"""
    mock_all_deps["run_pipeline"].side_effect = RuntimeError("pipeline failed")
    handler = get_handler()
    handler(context=None)  # ne doit pas lever d'exception


def test_email_recipient(mock_all_deps):
    """Test que l'email est envoyé au bon destinataire"""
    mock_all_deps["run_pipeline"].side_effect = RuntimeError("oops")
    handler = get_handler()
    handler(context=None)
    _, kwargs = mock_all_deps["send_ses_email"].call_args
    assert kwargs.get("recipient_email") == "data@soongo.co"


def test_email_sender(mock_all_deps):
    """Test que l'email a le bon expéditeur"""
    mock_all_deps["run_pipeline"].side_effect = RuntimeError("oops")
    handler = get_handler()
    handler(context=None)
    _, kwargs = mock_all_deps["send_ses_email"].call_args
    assert kwargs.get("sender_email") == "infra@soongo.co"


def test_email_subject_contains_alert(mock_all_deps):
    """Test que le sujet contient 'Alert'"""
    mock_all_deps["run_pipeline"].side_effect = RuntimeError("oops")
    handler = get_handler()
    handler(context=None)
    _, kwargs = mock_all_deps["send_ses_email"].call_args
    assert "Alert" in kwargs.get("subject", "")


def test_email_subject_mentions_sell_cost(mock_all_deps):
    """Test que le sujet mentionne Sell Cost"""
    mock_all_deps["run_pipeline"].side_effect = RuntimeError("oops")
    handler = get_handler()
    handler(context=None)
    _, kwargs = mock_all_deps["send_ses_email"].call_args
    assert "Sell Cost" in kwargs.get("subject", "")


def test_handles_file_not_found(mock_all_deps):
    """Test gestion FileNotFoundError pour config.yaml"""
    with patch("builtins.open", side_effect=FileNotFoundError("no config")):
        handler = get_handler()
        handler(context=None)  # ne doit pas lever d'exception
    mock_all_deps["send_ses_email"].assert_called_once()


def test_handles_secret_error(mock_all_deps):
    """Test gestion erreur de récupération des secrets"""
    mock_all_deps["get_local_secret"].side_effect = Exception("secret error")
    handler = get_handler()
    handler(context=None)  # ne doit pas lever d'exception
    mock_all_deps["send_ses_email"].assert_called_once()