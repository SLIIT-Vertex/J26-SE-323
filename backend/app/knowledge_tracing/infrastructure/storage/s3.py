from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.knowledge_tracing.infrastructure.storage.base import (
    StorageKeyNotFound,
    validate_key,
)

_MISSING_CODES = {"NoSuchKey", "404", "NotFound"}


class S3Storage:
    """Stores objects in a private S3 bucket. Credentials come from the standard AWS chain."""

    def __init__(self, bucket: str, region: str | None = None, client: Any = None) -> None:
        if not bucket:
            raise ValueError("S3_BUCKET is required for the s3 storage backend")
        self.bucket = bucket
        self._client = client or boto3.client("s3", region_name=region or None)

    def get(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=validate_key(key))
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in _MISSING_CODES:
                raise StorageKeyNotFound(key) from error
            raise
        return response["Body"].read()

    def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        extra = {"ContentType": content_type} if content_type else {}
        self._client.put_object(Bucket=self.bucket, Key=validate_key(key), Body=data, **extra)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=validate_key(key))
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in _MISSING_CODES:
                return False
            raise
        return True

    def list(self, prefix: str = "") -> list[str]:
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(item["Key"] for item in page.get("Contents", []))
        return sorted(keys)

    def delete(self, key: str) -> None:
        if not self.exists(key):
            raise StorageKeyNotFound(key)
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def signed_url(self, key: str, expires_seconds: int) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": validate_key(key)},
            ExpiresIn=expires_seconds,
        )
