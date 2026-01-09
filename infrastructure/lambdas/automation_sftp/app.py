import os
import re
import traceback
import urllib.parse

import yaml

from soongo_data.connectors import ConnectorData
from soongo_data.input_tables.upload_to_db import main as db_uploader
from soongo_data.utils.aws import send_ses_email
from soongo_data.utils.input_tables import input_table_dict
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.secrets_utils import get_local_secret


def generate_include_tables(con_name, lst, key):
    return {
        "include_tables": [
            [con_name.upper(), dataset, data_source, key]
            for dataset, data_source in lst
        ]
    }


def lambda_handler(event, context):
    key = event['Records'][0]['s3']['object']['key']
    key = urllib.parse.unquote_plus(key)
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    logger = gen_logger(os.environ['AWS_LAMBDA_FUNCTION_NAME'])

    try:
        organization_name, connector = os.path.dirname(key).split(os.sep)
        filename = os.path.basename(key)
        conf = yaml.safe_load(open('config.yaml', 'r'))

        # Execute db_uploader on the organization, connector and input_tables indicated by the upload_params
        sftp_params = [
            trigger for trigger in conf[connector]
            if re.match(trigger['filename_pattern'], filename)
        ]
        if len(sftp_params) == 0:
            raise ValueError(
                f'No input_tables found for connector {connector} '
                f'with filename_pattern matching {filename}'
            )
        if len(sftp_params) > 1:
            raise ValueError(
                f'More than one input_tables found for connector {connector} '
                f'with filename_pattern matching {filename}: {sftp_params}'
            )

        sftp_param = sftp_params[0]
        data_sources = sftp_param['data_sources']
        fetch_params = generate_include_tables(
            connector,
            data_sources,
            key,
        )

        # Get db info
        db_info = get_local_secret(
            logger=logger,
        )
        os.environ['DATABASE_URL'] = db_info['DATABASE_URL']
        update_values = sftp_param.get('update_values', 'overwrite')
        for input_table_name in sftp_param['input_tables']:
            logger.info(
                'Running upload on organization name %s, input_tables %s, fetch_params %s, update_value %s',
                organization_name,
                input_table_name,
                fetch_params,
                update_values
            )
            connector_data = ConnectorData(
                s3_bucket=bucket_name,
                root_folder='',
                organization_name=organization_name,
            )
            input_table = input_table_dict[input_table_name]
            logger.info(
                'Running db_upload on input_table %s',
                input_table.name,
            )
            db_uploader(
                input_table=input_table,
                connector_data=connector_data,
                logger=logger,
                database_url=db_info['DATABASE_URL'],
                fetch_params_dict=fetch_params,
                update_values=update_values,
            )
        logger.info(
            'Running upload on organization name %s, input_tables %s, fetch_params %s, update_value %s',
            organization_name,
            input_table_name,
            fetch_params,
            update_values
        )
        connector_data = ConnectorData(
            s3_bucket=bucket_name,
            root_folder='',
            organization_name=organization_name,
        )
        input_table = input_table_dict[input_table_name]
        logger.info(
            'Running db_upload on input_table %s',
            input_table.name,
        )
        db_uploader(
            input_table=input_table,
            connector_data=connector_data,
            logger=logger,
            database_url=db_info['DATABASE_URL'],
            fetch_params_dict=fetch_params,
            update_values='overwrite',
        )
    except Exception as error:
        logger.error(
            'SFTP upload for %s failed on error %s with traceback %s',
            key,
            error,
            traceback.format_exception(error),
        )
        send_ses_email(
            sender_email="infra@soongo.co",
            recipient_email="data@soongo.co",
            subject="Alert: Error on sftp automation",
            body_text=(
                f"SFTP automation for key {key} failed on error {error} "
                f"with traceback {traceback.format_exception(error)}"
            ),
            logger=logger,
        )
