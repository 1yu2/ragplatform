from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import GenerateRequest, GenerateResponse
from app.services.task_service import TaskService

router = APIRouter(prefix="/api", tags=["generate"])


@router.post("/generate", response_model=GenerateResponse)
def generate_image(payload: GenerateRequest) -> GenerateResponse:
    service = TaskService()
    task_id = service.create_and_run_task(payload)
    row = service.get_task(task_id)
    return GenerateResponse(task_id=task_id, status=row.status if row else "queued")


@router.get("/generate/{task_id}/events")
def task_events(task_id: str):
    service = TaskService()
    states = service.get_events(task_id)

    def event_stream():
        for state in states:
            yield f"data: {state}\n\n"
            time.sleep(0.12)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
