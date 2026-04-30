from pathlib import Path

from botocore.client import BaseClient as S3Client
from boto3 import client as boto3_client
from botocore.exceptions import ClientError

from app.models.document import Document
from app.models.organization import Organization
from app.settings.s3 import s3_settings
from app.service.storage.base import StorageService


def _build_s3_client() -> S3Client:
    return boto3_client(
        "s3",
        endpoint_url=s3_settings.endpoint_url,
        aws_access_key_id=s3_settings.access_key_id,
        aws_secret_access_key=s3_settings.secret_access_key,
        region_name=s3_settings.region,
    )


class S3StorageService(StorageService):
    def __init__(self):
        self._client: S3Client = _build_s3_client()

    def store(
        self,
        organization: Organization,
        document: Document,
        path: Path,
    ) -> None:
        if not document.name:
            msg = "Empty document's name"
            raise ValueError(msg)
        self._client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=raw_content,
            ContentType=document.content_type or "application/octet-stream",
        )

    def remove(self, document: Document, path: Path) -> None:
        pass

    def _ensure_bucket_exists(self, bucket_name: str) -> None:
        try:
            self._client.head_bucket(Bucket=bucket_name)
        except ClientError:
            self._client.create_bucket(Bucket=bucket_name)
