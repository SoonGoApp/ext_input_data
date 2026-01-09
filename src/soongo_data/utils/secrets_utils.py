import logging
import os

import yaml

from soongo_data.utils.aws import get_aws_secret


class SecretsNotFound(Exception):

    def __init__(self, env: str, secret_name: str):
        super().__init__(
            (
                f'{secret_name} secrets for environment {env} cannot'
                f'be fetched through the secret manager nor through an api '
                f'secrets file.'
            )
        )


def get_local_secret(
    logger: logging.Logger,
    secret_name: str = 'workers',
    region_name: str = "eu-west-3",
) -> dict:
    env = os.environ['env']
    try:
        return get_aws_secret(
            secret_name=f'{env}-{secret_name}-secrets',
            region_name=region_name,
        )

    except Exception:
        logger.warning(
            'Fetch data through AWS Secrets Manager failed for env %s and'
            'secret %s on region %s, attemping the local secrets.yaml, if any',
            env,
            secret_name,
            region_name,
        )
        secrets_path = os.path.join(
            os.environ['credentials_folder'],
            'env_secrets.yaml',
        )
        if not os.path.isfile(secrets_path):
            raise SecretsNotFound(
                env=env,
                secret_name=secret_name,
            )

        try:
            with open(secrets_path, 'r') as file:
                secret_dict = yaml.safe_load(file)
                return secret_dict[f'{env}-{secret_name}-secrets']
        except KeyError:
            raise SecretsNotFound(
                env=env,
                secret_name=secret_name,
            )
