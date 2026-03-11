from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, create_engine

from app.core.config import get_settings


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    task_id: str = Field(primary_key=True, max_length=64)
    session_id: str = Field(max_length=128, index=True)
    new_id: str = Field(max_length=128, index=True)
    status: str = Field(max_length=32, index=True)

    retry_count: int = Field(default=0)
    selected_ref_id: Optional[str] = Field(default=None, max_length=128)
    top3_ref_ids: Optional[str] = Field(default=None)

    style_prompt: Optional[str] = Field(default=None)
    final_prompt: Optional[str] = Field(default=None)

    image_model: Optional[str] = Field(default=None, max_length=256)
    llm_model: Optional[str] = Field(default=None, max_length=256)
    embed_model: Optional[str] = Field(default=None, max_length=256)

    latency_ms: Optional[int] = Field(default=None)

    sim_warning: bool = Field(default=False)
    sim_score: Optional[float] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TaskAsset(SQLModel, table=True):
    __tablename__ = "task_assets"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: str = Field(max_length=64, index=True)
    asset_type: str = Field(max_length=32, index=True)
    object_key: str = Field(max_length=512)
    presigned_url: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class Feedback(SQLModel, table=True):
    __tablename__ = "feedback"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: str = Field(max_length=64, index=True)
    feedback_type: str = Field(max_length=16, index=True)
    feedback_text: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: Optional[str] = Field(default=None, max_length=64, index=True)
    event_type: str = Field(max_length=64, index=True)
    payload: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


settings = get_settings()
engine = create_engine(settings.sqlite_url, echo=settings.debug)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
