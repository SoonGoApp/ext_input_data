import os

import boto3
import pandas as pd
import yaml

from soongo_data.utils.secrets_utils import get_local_secret
from soongo_data.utils.emails import (
    EmailPipelineDispatcher, authenticate_gmail, download_emails
)
from soongo_data.utils.logging_utils import gen_logger

ENV_BUCKET_DICT = {
    'prod': 'soongo-production',
    'staging': 'soongo-staging-data',
}


def lambda_handler(event, context):
    logger = gen_logger(
        name='gmail_api',
    )
    gmail_service = authenticate_gmail()
    emails = download_emails(
        service=gmail_service,
        date_from=pd.Timestamp.now() - pd.Timedelta(days=1),
        date_to=pd.Timestamp.now(),
    )
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'config.yaml',
    )
    with open(config_path, 'r') as file:
        email_dispatch_config = yaml.safe_load(file)

    db_info = get_local_secret(
        logger=logger,
    )
    os.environ['DATABASE_URL'] = db_info['DATABASE_URL']

    profile_name = event.get('profile_name')
    if profile_name:
        aws_session = boto3.Session(profile_name=profile_name)
        s3_client = aws_session.client('s3')
    else:
        s3_client = boto3.client('s3')

    dispatcher = EmailPipelineDispatcher(
        logger=logger,
        config=email_dispatch_config,
        s3_client=s3_client,
        s3_bucket=ENV_BUCKET_DICT[os.environ['env']],
        root_folder=os.environ.get('_soongo_data_folder', ''),
    )
    for email in emails:
        dispatcher.dispatch(email)


if __name__ == '__main__':
    lambda_handler(
        event={
            'profile_name': 'staging-s3-uploader',
        },
        context=None
    )
