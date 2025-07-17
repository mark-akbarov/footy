import uuid
from io import BytesIO

import boto3
from core.config import settings
from botocore.exceptions import ClientError
import os


def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )


def upload_cv_to_s3(file_obj: BytesIO, filename: str, content_type: str) -> str:
    s3 = get_s3_client()

    ext = os.path.splitext(filename)[1]
    key = f"cv_files/{uuid.uuid4()}{ext}"

    s3.upload_fileobj(
        Fileobj=file_obj,
        Bucket=settings.AWS_S3_BUCKET_NAME,
        Key=key,
        ExtraArgs={"ContentType": content_type}
    )

    return key


def delete_file_from_s3(s3_key: str):
    s3 = get_s3_client()
    try:
        s3.delete_object(Bucket=settings.AWS_S3_BUCKET_NAME, Key=s3_key)
    except ClientError as e:
        raise RuntimeError(f"Error deleting from S3: {e}")


def generate_presigned_url(s3_key: str, expiration: int = 3600) -> str:
    s3 = get_s3_client()
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_S3_BUCKET_NAME, "Key": s3_key},
            ExpiresIn=expiration
        )
        return url
    except ClientError as e:
        raise RuntimeError(f"Error generating presigned URL: {e}")
