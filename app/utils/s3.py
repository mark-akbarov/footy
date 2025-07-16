# utils/s3.py

import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError
from typing import IO
import uuid
import os

from urllib.parse import urlparse
from core.config import settings

AWS_ACCESS_KEY = settings.AWS_ACCESS_KEY_ID
AWS_SECRET_KEY = settings.AWS_SECRET_ACCESS_KEY
AWS_REGION = settings.AWS_REGION
AWS_BUCKET_NAME = settings.AWS_S3_BUCKET_NAME

s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)


def upload_file_to_s3(file: IO, filename: str, folder: str = "") -> str:
    try:
        file_extension = filename.split('.')[-1]
        key = f"{folder}/{uuid.uuid4()}.{file_extension}" if folder else f"{uuid.uuid4()}.{file_extension}"

        s3_client.upload_fileobj(file, AWS_BUCKET_NAME, key, ExtraArgs={"ACL": "public-read"})

        return f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{key}"
    except (BotoCoreError, NoCredentialsError) as e:
        raise RuntimeError(f"Failed to upload file to S3: {e}")


def delete_file_from_s3(file_url: str):
    """
    Deletes a file from an S3 bucket.

    :param file_url: The public URL of the file to delete.
    """
    try:
        parsed_url = urlparse(file_url)
        # The key is the path component of the URL, without the leading slash
        key = parsed_url.path.lstrip('/')
        s3_client.delete_object(Bucket=AWS_BUCKET_NAME, Key=key)
    except (BotoCoreError, NoCredentialsError) as e:
        raise RuntimeError(f"Failed to delete file from S3: {e}")


def download_file_from_s3(file_url: str) -> bytes:
    """
    Downloads a file from an S3 bucket.

    :param file_url: The public URL of the file to download.
    :return: The content of the file as bytes.
    """
    try:
        parsed_url = urlparse(file_url)
        # The key is the path component of the URL, without the leading slash
        key = parsed_url.path.lstrip('/')
        response = s3_client.get_object(Bucket=AWS_BUCKET_NAME, Key=key)
        return response['Body'].read()
    except (BotoCoreError, NoCredentialsError) as e:
        raise RuntimeError(f"Failed to download file from S3: {e}")


def generate_presigned_url(key, expires_in=3600):
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.AWS_BUCKET_NAME, "Key": key},
        ExpiresIn=expires_in
    )
