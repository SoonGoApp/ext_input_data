from __future__ import annotations

import base64
import logging
import os
import re
import shutil
import typing

from boto3 import client as boto3_client
from dataclasses import dataclass
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource

from soongo_data.connectors import ConnectorData
from soongo_data.input_tables.upload_to_db import main as upload_to_db, input_table_dict
from soongo_data.utils.logging_utils import gen_logger

if typing.TYPE_CHECKING:
    import pandas as pd


@dataclass
class Attachment:
    filename: str
    data: bytes


@dataclass
class Email:
    id: str
    subject: str
    sender: str
    recipients: typing.Set[str]
    attachments: typing.List[Attachment]
    reply_to: typing.Optional[str] = None


@dataclass
class EmailPipeline:
    organization_slug: str
    connector_name: str
    dataset_name: str
    dataset_type: str
    datasource_name: str
    input_tables: typing.Dict[str, typing.Dict]


class EmailPipelineDispatcher:

    def __init__(
        self,
        logger: logging.Logger,
        config: list,
        s3_client: boto3_client,
        s3_bucket: str,
        root_folder: str,
    ):
        self.logger = logger
        self.config = config
        self.s3_client = s3_client
        self.s3_bucket = s3_bucket
        self.root_folder = root_folder

    def dispatch(self, email: Email) -> typing.Optional(EmailPipeline):

        self.logger.info(
            'Dispatching email %s with subject %s, from %s to %s',
            email.id,
            email.subject,
            email.sender,
            email.recipients,
        )

        for dispatch_conf in self.config:

            is_match = True
            for condition, pattern in dispatch_conf['conditions'].items():
                email_attribute = getattr(email, condition)
                if isinstance(email_attribute, str):
                    is_match = is_match and re.match(
                        pattern,
                        email_attribute,
                    )
                else:
                    attr_match = False
                    for item in email_attribute:
                        attr_match |= re.match(
                            pattern,
                            item,
                        )
                    is_match = is_match and attr_match

                if not is_match:
                    break

            if is_match:
                self.logger.info(
                    'Email %s matched dispatch condition %s',
                    email.id,
                    dispatch_conf,
                )
                pipeline = EmailPipeline(**dispatch_conf['pipeline'])
                # TODO: add an attachment filtering logic
                for attachment in email.attachments:
                    file_key = self.get_s3_key(
                        organization_slug=pipeline.organization_slug,
                        connector_name=pipeline.connector_name,
                        dataset_type=pipeline.dataset_type,
                        dataset_name=pipeline.dataset_name,
                        filename=attachment.filename,
                    )
                    self.s3_client.put_object(
                        Body=attachment.data,
                        Bucket=self.s3_bucket,
                        Key=file_key
                    )
                    for input_table, fetch_params in pipeline.input_tables.items():
                        self.logger.info(
                            'Uploading attachment %s to input_table %s '
                            'with fetch_params %s',
                            attachment.filename,
                            input_table,
                            fetch_params,
                        )
                        fetch_params_dict = fetch_params.get('fetch_params_dict', {})
                        fetch_params_dict['include_tables'] = [
                            (
                                pipeline.connector_name,
                                pipeline.dataset_name,
                                pipeline.datasource_name,
                                file_key,
                            )
                        ]
                        fetch_params['fetch_params_dict'] = fetch_params_dict
                        connector_data = ConnectorData(
                            s3_bucket=self.s3_bucket,
                            root_folder=self.root_folder,
                            organization_name=pipeline.organization_slug,
                        )
                        upload_to_db(
                            logger=self.logger,
                            input_table=input_table_dict[input_table],
                            connector_data=connector_data,
                            database_url=os.environ['DATABASE_URL'],
                            **fetch_params,
                        )

    def get_s3_key(
        self,
        organization_slug: str,
        connector_name: str,
        dataset_type: str,
        dataset_name: str,
        filename: str,
    ) -> str:
        return (
            f'{organization_slug}/{connector_name}/{dataset_type}/'
            f'{dataset_name}/{filename}'
        )


def download_emails(
    service: Resource,
    date_from: pd.Timestamp = None,
    date_to: pd.Timestamp = None,
    user_id: str = 'me',
    base_query: str = 'has:attachment',
) -> typing.Generator[Email, None, None]:
    if date_from:
        base_query += f" after:{int(date_from.timestamp())}"
    if date_to:
        base_query += f" before:{int(date_to.timestamp())}"

    request = service.users().messages().list(userId=user_id, q=base_query)

    while request is not None:

        response = request.execute()
        messages = response.get('messages', [])
        request = service.users().messages().list_next(previous_request=request, previous_response=response)

        for message in messages:
            attachments = []
            msg = service.users().messages().get(userId=user_id, id=message['id']).execute()

            headers = msg['payload']['headers']

            # Sender and Subject necessarily unique, hence stop at first match
            sender = next((header['value'] for header in headers if header['name'] == 'From'), None)
            assert sender is not None, "Email without sender found"
            email_subject = next((header['value'] for header in headers if header['name'] == 'Subject'), None)
            assert email_subject is not None, "Email without sender found"
            recipients = next((header['value'] for header in headers if header['name'] == 'To'), None)
            assert recipients is not None, "Email without sender found"
            reply_to = next((header['value'] for header in headers if header['name'] == 'Reply-To'), None)

            for part in msg['payload'].get('parts', []):
                if part['filename']:
                    attachment_id = part['body']['attachmentId']
                    attachment = service.users().messages().attachments().get(
                        userId=user_id, messageId=message['id'], id=attachment_id
                    ).execute()
                    data = base64.urlsafe_b64decode(attachment['data'])
                    attachments.append(
                        Attachment(
                            filename=part['filename'],
                            data=data
                        )
                    )

            yield Email(
                id=message['id'],
                subject=email_subject,
                sender=sender,
                recipients=recipients,
                attachments=attachments,
                reply_to=reply_to,
            )


def authenticate_gmail() -> Resource:

    scopes = ['https://www.googleapis.com/auth/gmail.readonly']
    cred_path = os.path.join(
        os.environ['credentials_folder'],
        'gmail_credentials.json',
    )
    creds = None

    if os.path.exists(cred_path):
        if not os.access(cred_path, os.W_OK):
            # AWS lambdas store images in read-only filesystem
            # hence need to copy to /tmp before use for write access
            os.makedirs('/tmp', exist_ok=True)
            shutil.copy(cred_path, '/tmp/gmail_credentials.json')
            cred_path = '/tmp/gmail_credentials.json'

        creds = Credentials.from_authorized_user_file(
            filename=cred_path,
            scopes=scopes
        )

    # If no valid credentials, prompt the user to log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_file=cred_path,
                scopes=scopes
            )
            creds = flow.run_local_server(port=0)

        with open(cred_path, 'wb') as token:
            token.write(creds.to_json().encode('utf-8'))

    return build('gmail', 'v1', credentials=creds)


if __name__ == '__main__':
    logger = gen_logger(
        name='gmail_api',
    )
    gmail_service = authenticate_gmail()
    emails = download_emails(
        gmail_service,
        base_query='subject:"Etat de Parc Contrat et Véhicule"'
    )
    for email in emails:
        for attachment in email.attachments:
            filename = attachment.filename
            data = attachment.data
            with open(filename, 'wb') as f:
                f.write(data)
            logger.info(f'Downloaded {filename}')
