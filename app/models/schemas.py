from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    new_id: str = Field(min_length=1)
    aspect_ratio: str = Field(default="3:4")
    user_prompt_override: Optional[str] = None
    session_id: Optional[str] = None


class GenerateResponse(BaseModel):
    task_id: str
    status: str = "queued"


class IngestResponse(BaseModel):
    output_csv: str
    scanned_images: int
    written_rows: int
    skipped_rows: int
    duplicate_rows: int


class IngestStatusResponse(BaseModel):
    products_csv_rows: int
    new_products_csv_rows: int
    milvus_collection_exists: bool
    milvus_entity_count: int
    ready: bool


class FeedbackRequest(BaseModel):
    feedback_type: str
    feedback_text: Optional[str] = None


class TaskSummary(BaseModel):
    task_id: str
    new_id: str
    status: str
    created_at: datetime


class MetricsSummary(BaseModel):
    total_tasks: int
    success_rate: float
    dislike_rate: float
