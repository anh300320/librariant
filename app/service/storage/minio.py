from io import BytesIO
from pathlib import Path
from uuid import uuid4

import aioboto3
from botocore.exceptions import ClientError

from app.service.storage.base import AsyncStorageService, StoredObject
from app.settings.minio import MinioSettings


class AsyncMinioStorageService(AsyncStorageService):
    def __init__(self, settings: MinioSettings):
        self._session = aioboto3.Session()
        self._settings = settings
        self._bucket = settings.bucket
        self._client = self._session.client(
            service_name="s3",
            endpoint_url=self._settings.endpoint,
            aws_access_key_id=self._settings.access_key,
            aws_secret_access_key=self._settings.secret_key,
        )

    async def store(self, document: StoredObject) -> str:
        if document.content is None:
            msg = "Empty document content"
            raise ValueError(msg)

        bucket_name = self._bucket
        object_name = str(uuid4())
        await self._ensure_bucket_exists(bucket_name)

        data = BytesIO(document.content)
        await self._client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=data,
            length=len(document.content),
            content_type=document.content_type or "application/octet-stream",
        )
        return object_name

    async def remove(self, id: str) -> None:
        bucket_name = self._bucket
        await self._client.remove_object(
            bucket_name=bucket_name,
            object_name=id,
        )

    async def load(self, id: str) -> StoredObject:
        response = await self._client.get_object(
            Bucket=self._bucket,
            Key=id,
        )
        async with response["Body"] as stream:
            raw_content = await stream.read()

        return StoredObject(
            id=id,
            content_type=response.get("ContentType"),
            raw_content=raw_content,
            kb_size=len(raw_content) // 1024,
        )

    async def _ensure_bucket_exists(self, bucket_name: str) -> None:
        try:
            await self._client.head_bucket(Bucket=bucket_name)
        except ClientError:
            await self._client.create_bucket(Bucket=bucket_name)