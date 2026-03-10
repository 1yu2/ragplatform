from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from app.core.constants import TaskStatus
from app.repositories.sqlite_repo import now_iso
from app.utils.hash_util import sha256_bytes


class FileService:
    def __init__(self, sqlite_repo, minio_repo, ingestion_service):
        self.sqlite_repo = sqlite_repo
        self.minio_repo = minio_repo
        self.ingestion_service = ingestion_service

    def _safe_name(self, file_name: str) -> str:
        file_name = file_name.strip().replace(" ", "_")
        return re.sub(r"[^a-zA-Z0-9_.\-\u4e00-\u9fff]", "_", file_name)

    async def upload_pdf(self, file_name: str, content: bytes) -> dict:
        if not file_name:
            raise ValueError("file name is empty")
        if not content:
            raise ValueError("file content is empty")

        sha = sha256_bytes(content)
        existing = self.sqlite_repo.get_file_by_sha256(sha)
        if existing:
            task = self.sqlite_repo.get_task_by_file_id(existing["id"])
            return {
                "file_id": existing["id"],
                "task_id": task["id"] if task else "",
                "deduplicated": True,
            }

        file_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        object_key = f"kb/{file_id}/{ts}_{uuid.uuid4().hex[:8]}.pdf"

        self.minio_repo.upload_bytes(object_key=object_key, content=content, content_type="application/pdf")

        now = now_iso()
        self.sqlite_repo.create_file(
            {
                "id": file_id,
                "file_name": file_name,
                "sha256": sha,
                "size_bytes": len(content),
                "minio_object_key": object_key,
                "status": TaskStatus.QUEUED.value,
                "created_at": now,
                "updated_at": now,
            }
        )
        self.sqlite_repo.create_task(
            {
                "id": task_id,
                "file_id": file_id,
                "status": TaskStatus.QUEUED.value,
                "retry_count": 0,
                "error_message": None,
                "started_at": None,
                "finished_at": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        return {"file_id": file_id, "task_id": task_id, "deduplicated": False}

    def list_files(self, limit: int | None = None, offset: int = 0) -> list[dict]:
        return self.sqlite_repo.list_files(limit=limit, offset=offset)

    def count_files(self) -> int:
        return self.sqlite_repo.count_files()

    def get_preview(self, file_id: str) -> dict:
        return self.sqlite_repo.get_preview(file_id)

    def latest_task(self, file_id: str) -> dict | None:
        return self.sqlite_repo.get_task_by_file_id(file_id)

    async def reprocess(self, file_id: str) -> dict:
        file_record = self.sqlite_repo.get_file(file_id)
        if not file_record:
            raise ValueError("file not found")

        task_id = str(uuid.uuid4())
        now = now_iso()
        self.sqlite_repo.create_task(
            {
                "id": task_id,
                "file_id": file_id,
                "status": TaskStatus.QUEUED.value,
                "retry_count": 0,
                "error_message": None,
                "started_at": None,
                "finished_at": None,
                "created_at": now,
                "updated_at": now,
            }
        )

        return {"task_id": task_id}
