from fastapi import APIRouter

from app.models.schemas import MetricsSummary
from app.services.task_service import TaskService

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/summary", response_model=MetricsSummary)
def summary(days: int = 30) -> MetricsSummary:
    service = TaskService()
    total, success_rate, dislike_rate = service.metrics_summary(days=days)
    return MetricsSummary(total_tasks=total, success_rate=success_rate, dislike_rate=dislike_rate)
