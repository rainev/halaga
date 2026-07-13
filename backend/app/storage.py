"""Object storage via the S3 API (MinIO in dev, S3/Spaces in prod).

MinIO speaks S3, so we use boto3 pointed at the MinIO endpoint. Path-style
addressing is required for MinIO (bucket in the path, not the hostname).
"""

import boto3
from botocore.client import Config

from .env import env

BUCKET = env.MINIO_BUCKET

s3 = boto3.client(
    "s3",
    endpoint_url=env.MINIO_ENDPOINT,
    aws_access_key_id=env.MINIO_ROOT_USER,
    aws_secret_access_key=env.MINIO_ROOT_PASSWORD,
    region_name="us-east-1",  # arbitrary; MinIO ignores it but boto3 wants one
    config=Config(s3={"addressing_style": "path"}),
)


def ensure_bucket() -> None:
    """Safety net in case the one-shot minio-setup container hasn't created it."""
    try:
        s3.head_bucket(Bucket=BUCKET)
    except Exception:
        s3.create_bucket(Bucket=BUCKET)
        print(f'Created bucket "{BUCKET}"')
