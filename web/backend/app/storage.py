"""
Storage: upload audio files to S3-compatible object storage (Railway Volume or AWS S3).
Falls back to local /tmp storage if no S3 config is set (useful for dev).
"""
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_USE_S3 = bool(os.environ.get("AWS_BUCKET_NAME"))


def upload_audio(local_path: str, key: str) -> str:
    """Upload a local MP3 file and return its public URL."""
    if _USE_S3:
        return _upload_s3(local_path, key)
    return _upload_local(local_path, key)


def _upload_s3(local_path: str, key: str) -> str:
    import boto3
    bucket = os.environ["AWS_BUCKET_NAME"]
    region = os.environ.get("AWS_REGION", "us-east-1")
    endpoint = os.environ.get("AWS_ENDPOINT_URL")  # for R2 / MinIO

    kwargs = dict(region_name=region)
    if endpoint:
        kwargs["endpoint_url"] = endpoint

    s3 = boto3.client("s3", **kwargs)
    s3.upload_file(
        local_path, bucket, key,
        ExtraArgs={"ContentType": "audio/mpeg", "ACL": "public-read"},
    )
    if endpoint:
        return f"{endpoint}/{bucket}/{key}"
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


def _upload_local(local_path: str, key: str) -> str:
    """Dev fallback: serve from /tmp/audio via the /audio static mount."""
    dest = Path("/tmp/audio") / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(local_path, dest)
    base_url = os.environ.get("BASE_URL", "http://localhost:8000")
    return f"{base_url}/audio/{key}"
