from datetime import datetime
from typing import Any

from pydantic import BaseModel


class FileRecord(BaseModel):
    id: str
    file_name: str
    sha256: str
    size_bytes: int
    status: str
    created_at: datetime
    updated_at: datetime


class TaskRecord(BaseModel):
    id: str
    file_id: str
    status: str
    retry_count: int
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class FileUploadResult(BaseModel):
    file_id: str
    task_id: str
    deduplicated: bool


class FilePreviewResult(BaseModel):
    file_id: str
    blocks: list[dict[str, Any]]
    chunks: list[dict[str, Any]]
