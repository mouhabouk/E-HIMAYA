"""S3-compatible object storage (SeaweedFS): media evidence, institution documents, certificate PDFs.

boto3 is synchronous, so calls run in threads.
"""

import hashlib
from functools import lru_cache
from typing import Any, Protocol

import boto3
from anyio import to_thread
from botocore.config import Config

from app.core.config import get_settings

_CHUNK = 1024 * 1024


class ObjectStore(Protocol):
    async def sha256(self, key: str) -> tuple[str, int]: ...

    async def head(self, key: str, size: int) -> bytes: ...

    async def delete(self, *keys: str) -> None: ...

    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def presign_get(
        self,
        key: str,
        *,
        expires_s: int = 600,
        content_type: str | None = None,
        internal: bool = False,
        disposition: str | None = None,
    ) -> str: ...


class S3ObjectStore:
    def __init__(self) -> None:
        settings = get_settings()
        secret = settings.s3_secret_key.get_secret_value() if settings.s3_secret_key else None
        config = Config(signature_version="s3v4", s3={"addressing_style": "path"}, retries={"max_attempts": 3})
        common: dict[str, Any] = {
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": secret,
            "region_name": settings.s3_region,
            "config": config,
        }
        self._bucket = settings.s3_bucket_media
        self._client = boto3.client("s3", endpoint_url=settings.s3_endpoint_url, **common)
        public = settings.s3_public_endpoint_url or settings.s3_endpoint_url
        self._presigner = boto3.client("s3", endpoint_url=public, **common)

    def _sha256_sync(self, key: str) -> tuple[str, int]:
        body = self._client.get_object(Bucket=self._bucket, Key=key)["Body"]
        digest = hashlib.sha256()
        size = 0
        for chunk in body.iter_chunks(_CHUNK):
            digest.update(chunk)
            size += len(chunk)
        return digest.hexdigest(), size

    async def sha256(self, key: str) -> tuple[str, int]:
        """Stream the stored object and hash it (evidence integrity, NFR-07)."""
        return await to_thread.run_sync(self._sha256_sync, key)

    def _head_sync(self, key: str, size: int) -> bytes:
        body = self._client.get_object(Bucket=self._bucket, Key=key, Range=f"bytes=0-{size - 1}")["Body"]
        data: bytes = body.read(size)
        return data

    async def head(self, key: str, size: int) -> bytes:
        """The first ``size`` bytes of an object (magic-number type detection)."""
        return await to_thread.run_sync(self._head_sync, key, size)

    def _delete_sync(self, keys: tuple[str, ...]) -> None:
        self._client.delete_objects(Bucket=self._bucket, Delete={"Objects": [{"Key": k} for k in keys], "Quiet": True})

    async def delete(self, *keys: str) -> None:
        if keys:
            await to_thread.run_sync(self._delete_sync, keys)

    def _put_sync(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        """Store a server-generated object (certificate PDFs)."""
        await to_thread.run_sync(self._put_sync, key, data, content_type)

    def presign_get(
        self,
        key: str,
        *,
        expires_s: int = 600,
        content_type: str | None = None,
        internal: bool = False,
        disposition: str | None = None,
    ) -> str:
        """Short-lived read link: public address for browsers, internal address for the AI service.

        ``content_type`` and ``disposition`` override the stored headers of the response."""
        params: dict[str, str] = {"Bucket": self._bucket, "Key": key}
        if content_type:
            params["ResponseContentType"] = content_type
        if disposition:
            params["ResponseContentDisposition"] = disposition
        signer = self._client if internal else self._presigner
        url: str = signer.generate_presigned_url("get_object", Params=params, ExpiresIn=expires_s)
        return url


_store: ObjectStore | None = None


@lru_cache
def _default_store() -> S3ObjectStore:
    return S3ObjectStore()


def get_store() -> ObjectStore:
    return _store or _default_store()


def set_store(store: ObjectStore | None) -> None:
    """Used by tests to inject an in-memory store."""
    global _store
    _store = store
