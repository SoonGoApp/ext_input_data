import os
import traceback

from soongo_data.connectors import ConnectorData
from soongo_data.input_tables.upload_to_db import main as db_uploader
from soongo_data.utils.aws import get_aws_secret, send_ses_email
from soongo_data.utils.input_tables import input_table_dict
from soongo_data.utils.logging_utils import gen_logger


def lambda_handler(event, context):

    # Get db info
    db_info = get_aws_secret(secret_name=f'{os.environ['env']}-workers-secrets')
    logger = gen_logger('api_run')
    os.environ['DATABASE_URL'] = db_info['DATABASE_URL']

    for upload_params in event:
        # Execute db_uploader on the organization, connector and input_tables indicated by the upload_params
        organization_name = upload_params.get('organization_name')
        input_tables = upload_params.get('input_tables')
        fetch_params = upload_params.get('fetch_params')
        update_value = upload_params.get('update_value')
        columns = upload_params.get('columns')
        logger.info(
            (
                'Running upload on organization name %s, input_tables %s, '
                'fetch_params %s, update_value %s, and columns %s'
            ),
            organization_name,
            input_tables,
            fetch_params,
            update_value,
            columns,
        )

        try:
            connector_data = ConnectorData(
                s3_bucket=os.environ['DATA_S3_BUCKET'],
                root_folder='',
                organization_name=organization_name,
            )
            for input_table_name in input_tables:
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
                    update_values=upload_params['update_value'],
                    columns=columns,
                )
        except Exception as error:
            logger.error(
                (
                    'Refresh for organization %s, input_tables %s, '
                    'fetch_params %s, update_value %s, and columns %s '
                    'failed on error %s with traceback %s'
                ),
                organization_name,
                input_tables,
                fetch_params,
                update_value,
                columns,
                error,
                traceback.format_exception(error),
            )
            send_ses_email(
                sender_email="infra@soongo.co",
                recipient_email="data@soongo.co",
                subject="Alert: Error on synchronise connector",
                body_text=(
                    f"Refresh for organization {organization_name}, "
                    f"input_tables {input_tables}, fetch_params {fetch_params}"
                    f" and columns {columns} failed on error {error} "
                    f"with traceback {traceback.format_exception(error)}"
                ),
                logger=logger,
            )
