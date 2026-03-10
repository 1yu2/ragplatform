from __future__ import annotations

from fastapi import APIRouter, Depends

from app.container import get_container
from app.models.dto.common import ApiResponse

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/run", response_model=ApiResponse)
async def run_evaluation(container=Depends(get_container)):
    result = container.evaluation_service.run_once(dataset_size=50)
    return ApiResponse(data=result)


@router.get("/latest", response_model=ApiResponse)
async def latest_evaluation(container=Depends(get_container)):
    return ApiResponse(data=container.evaluation_service.latest())


@router.get("/history", response_model=ApiResponse)
async def history_evaluation(container=Depends(get_container)):
    return ApiResponse(data=container.evaluation_service.history(limit=100))
