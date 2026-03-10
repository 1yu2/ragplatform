from __future__ import annotations

from io import BytesIO
import logging
import re
from datetime import timedelta
from urllib.parse import quote, urlsplit

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class MinioRepo:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool = False):
        self.endpoint, self.secure = self._normalize_endpoint(endpoint=endpoint, secure=secure)
        self.bucket = self._normalize_bucket(bucket)
        self.client = Minio(
            self.endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=self.secure,
        )

    @staticmethod
    def _normalize_endpoint(endpoint: str, secure: bool) -> tuple[str, bool]:
        raw = endpoint.strip()
        if raw.startswith("http://") or raw.startswith("https://"):
            parts = urlsplit(raw)
            if parts.path not in ("", "/"):
                raise ValueError("MINIO_ENDPOINT should not contain path; use host:port only")
            host = parts.netloc
            return host, parts.scheme == "https"
        return raw, secure

    @staticmethod
    def _normalize_bucket(bucket: str) -> str:
        raw = bucket.strip()
        normalized = raw.replace("_", "-").lower()
        if normalized != raw:
            logger.warning("MINIO_BUCKET normalized from '%s' to '%s' (S3 naming rules).", raw, normalized)

        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", normalized):
            raise ValueError(
                f"invalid bucket name '{raw}'. Use 3-63 chars: lowercase letters, numbers, dot, hyphen."
            )
        return normalized

    def ensure_bucket(self) -> None:
        found = self.client.bucket_exists(self.bucket)
        if not found:
            self.client.make_bucket(self.bucket)

    def upload_bytes(self, object_key: str, content: bytes, content_type: str = "application/pdf") -> str:
        try:
            self.ensure_bucket()
            stream = BytesIO(content)
            self.client.put_object(
                self.bucket,
                object_key,
                stream,
                length=len(content),
                content_type=content_type,
            )
            return self.object_url(object_key)
        except S3Error as exc:
            raise RuntimeError(f"MinIO upload failed: {exc.code} - {exc.message}") from exc

    def object_url(self, object_key: str) -> str:
        scheme = "https" if self.secure else "http"
        encoded_key = quote(object_key, safe="/")
        return f"{scheme}://{self.endpoint}/{self.bucket}/{encoded_key}"

    def presigned_get_url(self, object_key: str, expires_seconds: int = 900) -> str:
        self.ensure_bucket()
        return self.client.presigned_get_object(
            bucket_name=self.bucket,
            object_name=object_key,
            expires=timedelta(seconds=expires_seconds),
        )

    def get_object_bytes(self, object_key: str) -> bytes:
        try:
            resp = self.client.get_object(self.bucket, object_key)
            data = resp.read()
            resp.close()
            resp.release_conn()
            return data
        except S3Error as exc:
            raise RuntimeError(f"MinIO get_object failed: {exc.code} - {exc.message}") from exc

    def remove_object(self, object_key: str) -> None:
        try:
            self.client.remove_object(self.bucket, object_key)
        except S3Error:
            return
