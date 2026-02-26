import pytest
from unittest.mock import patch, mock_open, MagicMock
from infrastructure.lambdas.home_station_eligibility.app import lambda_handler


@pytest.fixture
def mock_config():
    """Configuration YAML de test"""
    return {
        "database": {"schema": "test_schema"},
        "tables": {
            "input": {"collaborators_table": "collaborators"},
            "output": {"eligibility_table": "eligibility"}
        },
        "nb_rows_to_process": None
    }


class TestLambdaHandler:
    """Tests pour lambda_handler"""

    @patch('infrastructure.lambdas.home_station_eligibility.app.send_ses_email')
    @patch('infrastructure.lambdas.home_station_eligibility.app.get_local_secret')
    @patch('infrastructure.lambdas.home_station_eligibility.app.run_pipeline')
    @patch('infrastructure.lambdas.home_station_eligibility.app.yaml.safe_load')
    @patch('builtins.open', new_callable=mock_open)
    @patch('infrastructure.lambdas.home_station_eligibility.app.os.path.abspath')
    @patch('infrastructure.lambdas.home_station_eligibility.app.os.path.dirname')
    def test_lambda_handler_success(self, mock_dirname, mock_abspath, mock_file, mock_yaml, 
                                     mock_run_pipeline, mock_get_secret, mock_send_email, mock_config):
        """Test lambda handler réussi"""
        # Arrange
        mock_dirname.return_value = "/lambda/path"
        mock_abspath.return_value = "/lambda/path/app.py"
        mock_yaml.return_value = mock_config
        mock_get_secret.return_value = {"DATABASE_URL": "postgresql://test"}

        # Act
        result = lambda_handler(context=None)

        # Assert
        assert result == {"status": "success"}
        mock_run_pipeline.assert_called_once_with(config=mock_config)
        mock_file.assert_called_once()
        mock_send_email.assert_not_called()

    @patch('infrastructure.lambdas.home_station_eligibility.app.send_ses_email')
    @patch('infrastructure.lambdas.home_station_eligibility.app.get_local_secret')
    @patch('infrastructure.lambdas.home_station_eligibility.app.run_pipeline')
    @patch('infrastructure.lambdas.home_station_eligibility.app.yaml.safe_load')
    @patch('builtins.open', new_callable=mock_open)
    @patch('infrastructure.lambdas.home_station_eligibility.app.os.path.abspath')
    @patch('infrastructure.lambdas.home_station_eligibility.app.os.path.dirname')
    def test_lambda_handler_with_context(self, mock_dirname, mock_abspath, mock_file, mock_yaml, 
                                         mock_run_pipeline, mock_get_secret, mock_send_email, mock_config):
        """Test lambda handler avec contexte"""
        # Arrange
        mock_dirname.return_value = "/lambda/path"
        mock_abspath.return_value = "/lambda/path/app.py"
        mock_yaml.return_value = mock_config
        mock_get_secret.return_value = {"DATABASE_URL": "postgresql://test"}
        context = {"request_id": "test-123"}

        # Act
        result = lambda_handler(context=context)

        # Assert
        assert result == {"status": "success"}
        mock_run_pipeline.assert_called_once()

    @patch('infrastructure.lambdas.home_station_eligibility.app.send_ses_email')
    @patch('infrastructure.lambdas.home_station_eligibility.app.get_local_secret')
    @patch('infrastructure.lambdas.home_station_eligibility.app.run_pipeline')
    @patch('infrastructure.lambdas.home_station_eligibility.app.yaml.safe_load')
    @patch('builtins.open', new_callable=mock_open)
    @patch('infrastructure.lambdas.home_station_eligibility.app.os.path.abspath')
    @patch('infrastructure.lambdas.home_station_eligibility.app.os.path.dirname')
    def test_lambda_handler_pipeline_exception(self, mock_dirname, mock_abspath, mock_file, mock_yaml, 
                                                mock_run_pipeline, mock_get_secret, mock_send_email, mock_config):
        """Test lambda handler avec exception dans le pipeline"""
        # Arrange
        mock_dirname.return_value = "/lambda/path"
        mock_abspath.return_value = "/lambda/path/app.py"
        mock_yaml.return_value = mock_config
        mock_get_secret.return_value = {"DATABASE_URL": "postgresql://test"}
        mock_run_pipeline.side_effect = Exception("Pipeline error")

        # Act
        result = lambda_handler(context=None)

        # Assert
        assert result is None  # La fonction ne retourne rien en cas d'erreur
        mock_send_email.assert_called_once()  # Email d'erreur envoyé

    @patch('infrastructure.lambdas.home_station_eligibility.app.send_ses_email')
    @patch('infrastructure.lambdas.home_station_eligibility.app.get_local_secret')
    @patch('infrastructure.lambdas.home_station_eligibility.app.yaml.safe_load')
    @patch('builtins.open')
    @patch('infrastructure.lambdas.home_station_eligibility.app.os.path.abspath')
    @patch('infrastructure.lambdas.home_station_eligibility.app.os.path.dirname')
    def test_lambda_handler_config_file_not_found(self, mock_dirname, mock_abspath, mock_file, 
                                                   mock_yaml, mock_get_secret, mock_send_email):
        """Test lambda handler avec fichier config introuvable"""
        # Arrange
        mock_dirname.return_value = "/lambda/path"
        mock_abspath.return_value = "/lambda/path/app.py"
        mock_get_secret.return_value = {"DATABASE_URL": "postgresql://test"}
        mock_file.side_effect = FileNotFoundError("Config file not found")

        # Act
        result = lambda_handler(context=None)

        # Assert
        assert result is None  # La fonction ne retourne rien en cas d'erreur
        mock_send_email.assert_called_once()  # Email d'erreur envoyé

    @patch('infrastructure.lambdas.home_station_eligibility.app.send_ses_email')
    @patch('infrastructure.lambdas.home_station_eligibility.app.get_local_secret')
    @patch('infrastructure.lambdas.home_station_eligibility.app.run_pipeline')
    @patch('infrastructure.lambdas.home_station_eligibility.app.yaml.safe_load')
    @patch('builtins.open', new_callable=mock_open)
    @patch('infrastructure.lambdas.home_station_eligibility.app.os.path.abspath')
    @patch('infrastructure.lambdas.home_station_eligibility.app.os.path.dirname')
    def test_lambda_handler_invalid_yaml(self, mock_dirname, mock_abspath, mock_file, mock_yaml, 
                                         mock_run_pipeline, mock_get_secret, mock_send_email):
        """Test lambda handler avec YAML invalide"""
        # Arrange
        mock_dirname.return_value = "/lambda/path"
        mock_abspath.return_value = "/lambda/path/app.py"
        mock_get_secret.return_value = {"DATABASE_URL": "postgresql://test"}
        mock_yaml.side_effect = Exception("Invalid YAML")

        # Act
        result = lambda_handler(context=None)

        # Assert
        assert result is None
        mock_run_pipeline.assert_not_called()
        mock_send_email.assert_called_once()  # Email d'erreur envoyé