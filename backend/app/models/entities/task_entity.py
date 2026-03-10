from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class TaskEntity:
    id: str
    file_id: str
    status: str
    retry_count: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
