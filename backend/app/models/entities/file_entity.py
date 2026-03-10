from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class FileEntity:
    id: str
    file_name: str
    sha256: str
    size_bytes: int
    minio_object_key: str
    status: str
    created_at: datetime
    updated_at: datetime
