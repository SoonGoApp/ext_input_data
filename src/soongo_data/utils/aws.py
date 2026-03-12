from __future__ import annotations

import json
import logging
from operator import itemgetter
import os
import re
import typing
import urllib
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import BytesIO, StringIO
from typing import Optional
from collections import defaultdict
import zipfile

import pandas as pd

import boto3
from botocore.exceptions import (ClientError, NoCredentialsError,
                                 PartialCredentialsError, BotoCoreError)
from aiobotocore.session import AioSession


def get_aws_secret(
    secret_name: str = 'staging-workers-secrets',
    region_name: str = "eu-west-3",
) -> dict:

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    get_secret_value_response = client.get_secret_value(
        SecretId=secret_name
    )

    return json.loads(get_secret_value_response['SecretString'])


def check_file_exists(
    s3_bucket: str,
    file_path: str,
    region_name: str = "eu-west-3",
) -> bool:

    s3_client = boto3.client(
        service_name='s3',
        region_name=region_name
    )

    if not file_path:  # Check bucket only
        try:
            s3_client.head_bucket(
                Bucket=s3_bucket,
            )
            return True
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                return False
            else:
                raise

    try:
        s3_client.head_object(Bucket=s3_bucket, Key=file_path)
        return True
    except ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            return False
        else:
            raise


def get_s3_url(
    s3_bucket: str,
    file_path: str,
    region_name: str = "eu-west-3",
):
    path, file_name = os.path.split(file_path)
    file_name = urllib.parse.quote_plus(file_name)
    file_path = os.path.join(path, file_name)
    return f"https://{s3_bucket}.s3.{region_name}.amazonaws.com/{file_path}"


def load_file_from_s3(
    s3_bucket: str,
    file_path: str,
    return_type: str,
    region_name: str = "eu-west-3",
    encoding: str = 'utf-8',
) -> typing.Union[StringIO, BytesIO]:

    return_dict = {
        'string': StringIO,
        'bytes': BytesIO,
        'raw_bytes': None,
    }
    if return_type not in return_dict:
        raise KeyError(
            f'Return type argument must be one of {return_dict.keys()}'
        )

    if not check_file_exists(
        s3_bucket=s3_bucket,
        file_path=file_path,
        region_name=region_name,
    ):
        raise FileNotFoundError(
            f'The passed file {file_path} does not exist on the s3 bucket'
            f' {s3_bucket}'
        )

    s3_client = boto3.client(
        service_name='s3',
        region_name=region_name
    )
    response = s3_client.get_object(
        Bucket=s3_bucket,
        Key=file_path,
    )['Body']

    if return_type == 'string':
        return return_dict[return_type](response.read().decode(encoding))
    elif return_type == 'bytes':
        return return_dict[return_type](response.read())
    else:
        return response


def s3_list_objects(
    bucket_name: str,
    prefix: str,
    pattern: str = '.*',
) -> typing.List[str]:
    """
    List objects in an S3 bucket with a specific prefix and pattern.

    :param s3_bucket: Name of the S3 bucket.
    :param prefix: Prefix to filter objects.
    :param pattern: Regular expression pattern to match object keys.

    :returns: List of object keys matching the pattern.
    """
    try:
        s3 = boto3.client('s3')

        # List objects in the S3 bucket with the given prefix
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

        if 'Contents' not in response:
            raise FileNotFoundError(
                f'No files found in the bucket {bucket_name} with prefix '
                f'{prefix}'
            )

        # Filter objects based on the pattern
        matching_files = []

        for obj in response['Contents']:
            filename = os.path.basename(obj['Key'])
            if re.search(
                re.compile(pattern, re.IGNORECASE),
                filename,
            ) and not filename.endswith('/'):
                matching_files.append(obj)

        if not matching_files:
            raise FileNotFoundError(
                f'No files matching the pattern {pattern} found in the bucket '
                f'{bucket_name} with prefix {prefix}'
            )

        return matching_files
    except NoCredentialsError:
        raise ValueError('AWS credentials not available')
    except PartialCredentialsError:
        raise ValueError('Incomplete AWS credentials')


def s3_list_files(bucket_name, prefix, pattern):
    try:
        return list(map(
                itemgetter('Key'),
                s3_list_objects(
                    bucket_name=bucket_name,
                    prefix=prefix,
                    pattern=pattern,
                )
                ))
    except Exception as e:
        raise FileNotFoundError(
            f'No files matching the pattern {pattern} found in the bucket '
            f'{bucket_name} with prefix {prefix}'
        ) from e


def s3_get_most_recent_file(bucket_name, prefix, pattern):
    try:
        # Get the last modified time for each object
        return max(
            s3_list_objects(
                bucket_name=bucket_name,
                prefix=prefix,
                pattern=pattern,
            ),
            key=itemgetter('LastModified')
        )['Key']
    except NoCredentialsError:
        raise ValueError('AWS credentials not available')
    except PartialCredentialsError:
        raise ValueError('Incomplete AWS credentials')


def get_s3_file_creation_date(
    bucket_name: str,
    file_key: str,
) -> datetime:
    """
    Get the creation date of an S3 file using explicit AWS credentials.

    :param bucket_name: Name of the S3 bucket
    :param file_key: Key (path) of the file in the bucket
    :param aws_access_key_id: AWS access key ID
    :param aws_secret_access_key: AWS secret access key
    :param region_name: AWS region name

    Returns: datetime object representing the file's last modified date
    """
    # Get S3 client from session
    s3_client = boto3.client('s3')

    # Get object metadata
    try:
        response = s3_client.head_object(Bucket=bucket_name, Key=file_key)

        return response['LastModified']

    except ClientError:
        raise FileNotFoundError(
            'Passed file %s does not exist on bucket %s',
            file_key,
            bucket_name,
        )


def send_ses_email(
    body_text: str,
    subject: str,
    recipient_email: str,
    logger: logging.Logger,
    attachment_tup: typing.Tuple[str, bytes] = tuple(),
    raise_error: bool = False,
    sender_email: str = 'infra@soongo.co',
    s3_region: str = "eu-west-3",
) -> None:
    ses_client = boto3.client('ses', region_name=s3_region)

    try:
        mime_msg = format_mime_message(
            subject=subject,
            sender_email=sender_email,
            recipient=recipient_email,
            text=body_text,
            attachment_tup=attachment_tup,
        )
        response = ses_client.send_raw_email(
            Source=sender_email,
            Destinations=[recipient_email],
            RawMessage={
                'Data': mime_msg.as_string()
            }
        )
        logger.info(f"Email sent! Message ID: {response['MessageId']}")
    except Exception as e:
        if raise_error:
            raise e
        else:
            logger.error("Error sending email: %s", e)


def format_mime_message(
    subject: str,
    sender_email: str,
    recipient: str,
    text: str,
    attachment_tup: typing.Tuple[str, bytes],
    charset: str = "utf-8"
):
    """
    Formats the report as a MIME message. When the the email contains an attachment,
    it must be sent in MIME format.
    """
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient
    msg_body = MIMEMultipart("alternative")

    textpart = MIMEText(text, "plain", charset)
    msg_body.attach(textpart)
    msg.attach(msg_body)

    if attachment_tup:
        att = MIMEApplication(attachment_tup[1])
        att.add_header(
            "Content-Disposition",
            "attachment",
            filename=attachment_tup[0],
        )
        msg.attach(att)

    return msg


def df_to_bytes_csv(df: pd.DataFrame, encoding: str = 'utf-8') -> bytes:
    # Convert DataFrame to CSV string
    bytes_buffer = BytesIO()
    df.to_csv(bytes_buffer, index=False, encoding=encoding)

    return bytes_buffer.getvalue()


def df_to_bytes_excel(
    df: pd.DataFrame,
    sheet_name: str = 'Sheet1',
) -> bytes:
    # Convert DataFrame to Excel bytes
    bytes_buffer = BytesIO()
    with pd.ExcelWriter(bytes_buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)

    return bytes_buffer.getvalue()


def df_to_bytes_zipped_excel(
    df: pd.DataFrame,
    sheet_name: str = 'Sheet1',
    zip_filename: str = 'data.xlsx'
) -> bytes:
    """
    Convert a DataFrame to an Excel file and return the zipped version as bytes.

    :param df: The DataFrame to convert.
    :param sheet_name: The name of the Excel sheet.
    :param zip_filename: The name of the Excel file inside the zip archive.
    :return: Bytes of the zipped file.
    """
    # Convert DataFrame to Excel bytes
    excel_bytes = df_to_bytes_excel(df, sheet_name)

    # Create a zip file containing the Excel file
    zip_bytes = BytesIO()
    with zipfile.ZipFile(zip_bytes, mode='w', compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(zip_filename, excel_bytes)

    # Return the zipped content as bytes
    return zip_bytes.getvalue()


def gen_s3_path(
    organization_slug: str,
    entity_type: str,
    entity_id: str,
    document_type: str,
    file_name: str,
) -> str:
    """
    Generate the S3 path for a file based on organization slug, vehicle ID, document type, and file name.
    :param organization_slug: The slug of the organization.
    :param vehicle_id: The ID of the vehicle.
    :param document_type: The type of document.
    :param file_name: The name of the file.
    :returns: The S3 path for the file.
    """
    return os.path.join(
        organization_slug,
        'documents',
        entity_type,
        str(entity_id),
        document_type,
        file_name,
    )


async def push_to_s3_async(
    bucket_name: str,
    s3_path: str,
    content_type: str,
    content: bytes,
    logger: logging.Logger,
    session_profile: typing.Optional[str] = None,
    endpoint_url: typing.Optional[str] = None,
    ACL: typing.Optional[str] = None,
) -> None:
    """
    Push a file to an S3 bucket.

    :param bucket_name: Name of the S3 bucket.
    :param s3_path: path on which to store the file in S3.
    :param content_type: MIME type of the file.
    :param content: File content as bytes.
    :param logger: Logger for logging information.
    :param session_profile: AWS credentials profile name.
    :param endpoint_url: Custom endpoint URL for S3.
    :param ACL: Access control list setting for the uploaded file.

    """
    io_session = AioSession(profile=session_profile)

    try:
        async with io_session.create_client(
            's3',
            endpoint_url=endpoint_url,
        ) as s3_client:
            await s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_path,
                Body=content,
                ContentType=content_type,
                ACL=ACL,
            )
            logger.info(
                'File %s uploaded to S3 bucket %s',
                s3_path,
                bucket_name
            )

    except Exception as e:
        logger.error(
            'Error pushing file %s to S3: %s',
            bucket_name,
            str(e)
        )


def read_file_from_s3(bucket_name: str, object_key: str, encoding: str) -> str | None:
    """
    Reads a UTF-8 encoded text file from an S3 bucket and returns its content as a string.

    :param bucket_name: Name of the S3 bucket.
    :type bucket_name: str
    :param object_key: Full key (path) to the object in the bucket.
    :type object_key: str
    :return: The file content as a UTF-8 string, or None if an error occurred.
    :rtype: Optional[str]
    :raises: This function does not raise exceptions; errors are printed to stdout.
    """
    s3 = boto3.client('s3')
    try:
        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        return response['Body'].read().decode(encoding)
    except (BotoCoreError, ClientError, UnicodeDecodeError) as e:
        print(f"Error reading file from S3: {e}")
        return None



def push_folder_to_s3(
    local_dir: str,
    s3_prefix: str,
    bucket_name: str,
    region_name: str = "eu-west-3",
) -> None:
    """
    Upload a local folder recursively to S3 using default boto3 credentials,
    then delete the local folder.

    :param local_dir: Local directory to upload.
    :param s3_prefix: S3 prefix (folder) to upload into.
    :param bucket_name: Name of the S3 bucket.
    :param region_name: AWS region of the bucket.
    """
    s3 = boto3.client("s3", region_name=region_name)

    for root, _, files in os.walk(local_dir):
        for file in files:
            local_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_path, local_dir)
            s3_key = f"{s3_prefix}/{relative_path}".replace("\\", "/")

            try:
                s3.upload_file(local_path, bucket_name, s3_key)
            except Exception as e:
                print(f"Failed to upload {local_path}: {e}")


def get_most_recent_s3_model_name(
    bucket_name: str,
    prefix: str,
    region_name: str = "eu-west-3",
) -> Optional[str]:
    """
    Return the most recent folder name under an S3 prefix.
    """
    s3 = boto3.client("s3", region_name=region_name)

    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

    folder_last_modified = defaultdict(
        lambda: datetime.min.replace(tzinfo=timezone.utc)
    )

    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]

            if key.endswith("/"):
                continue

            relative_path = key[len(prefix):].lstrip("/")
            folder_name = relative_path.split("/", 1)[0]

            last_modified = obj["LastModified"] 

            if last_modified > folder_last_modified[folder_name]:
                folder_last_modified[folder_name] = last_modified

    if not folder_last_modified:
        return None

    return max(folder_last_modified, key=folder_last_modified.get)




def pull_folder_from_s3(
    s3_prefix: str,
    local_dir: str,
    bucket_name: str,
    region_name: str = "eu-west-3",
) -> None:
    """
    Download a folder from S3 recursively to a local directory using static credentials.
    """
    s3 = boto3.client("s3", region_name=region_name)

    os.makedirs(local_dir, exist_ok=True)

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name, Prefix=s3_prefix):
        for obj in page.get("Contents", []):
            s3_key = obj["Key"]

            relative_path = os.path.relpath(s3_key, s3_prefix)
            local_path = os.path.join(local_dir, relative_path)

            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            s3.download_file(bucket_name, s3_key, local_path)