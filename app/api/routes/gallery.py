from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException

from app.models.schemas import FeedbackRequest, TaskSummary
from app.services.task_service import TaskService

router = APIRouter(prefix="/api/gallery", tags=["gallery"])


@router.get("/tasks", response_model=list[TaskSummary])
def list_tasks() -> list[TaskSummary]:
    service = TaskService()
    rows = service.list_tasks()
    return [
        TaskSummary(
            task_id=r.task_id,
            new_id=r.new_id,
            status=r.status,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    service = TaskService()
    row = service.get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="task not found")

    generated_path = service.get_generated_asset_path(task_id)
    generated_image_url = f"/api/assets/local-image?path={quote(generated_path)}" if generated_path else None

    return {
        "task_id": row.task_id,
        "new_id": row.new_id,
        "status": row.status,
        "selected_ref_id": row.selected_ref_id,
        "top3_ref_ids": row.top3_ref_ids,
        "style_prompt": row.style_prompt,
        "final_prompt": row.final_prompt,
        "generated_image_url": generated_image_url,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


@router.post("/tasks/{task_id}/feedback")
def submit_feedback(task_id: str, payload: FeedbackRequest) -> dict:
    if payload.feedback_type not in {"up", "down"}:
        return {"ok": False, "error": "feedback_type must be 'up' or 'down'"}
    if payload.feedback_type == "down" and (not payload.feedback_text or len(payload.feedback_text.strip()) < 10):
        return {"ok": False, "error": "feedback_text must be at least 10 chars for down feedback"}

    service = TaskService()
    if not service.get_task(task_id):
        return {"ok": False, "error": "task not found"}

    service.upsert_feedback(task_id, payload.feedback_type, (payload.feedback_text or "").strip() or None)
    return {"ok": True, "task_id": task_id}
