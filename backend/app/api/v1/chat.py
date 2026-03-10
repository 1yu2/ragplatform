from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.container import get_container
from app.models.dto.chat_dto import ChatRequest
from app.models.dto.common import ApiResponse

router = APIRouter(prefix="/chat", tags=["chat"])


def _format_chat_log(item: dict) -> dict:
    citations = []
    raw = item.get("citations_json")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                citations = parsed
        except Exception:  # noqa: BLE001
            citations = []
    return {
        "id": item.get("id"),
        "question": item.get("question"),
        "rewritten_question": item.get("rewritten_question"),
        "answer": item.get("answer"),
        "is_refused": bool(item.get("is_refused")),
        "top1_score": float(item.get("top1_score") or 0.0),
        "latency_first_token_ms": item.get("latency_first_token_ms"),
        "created_at": item.get("created_at"),
        "citations": citations,
    }


@router.post("/stream")
async def chat_stream(payload: ChatRequest, container=Depends(get_container)):
    stream = container.chat_service.stream_answer(payload.question)
    return StreamingResponse(stream, media_type="text/event-stream")


@router.get("/history", response_model=ApiResponse)
async def chat_history(limit: int = 50, offset: int = 0, container=Depends(get_container)):
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    items = container.sqlite_repo.list_chat_logs(limit=limit, offset=offset)
    return ApiResponse(
        data={
            "items": [_format_chat_log(i) for i in items],
            "limit": limit,
            "offset": offset,
        }
    )


@router.get("/history/{chat_id}", response_model=ApiResponse)
async def chat_history_detail(chat_id: str, container=Depends(get_container)):
    item = container.sqlite_repo.get_chat_log(chat_id)
    if not item:
        return ApiResponse(code=1004, message="chat history not found", data=None)
    data = _format_chat_log(item)
    if not data.get("citations"):
        query = str(item.get("rewritten_question") or item.get("question") or "").strip()
        if query:
            try:
                citations = await container.chat_service.build_citations_for_query(query)
                if citations:
                    container.sqlite_repo.update_chat_citations(chat_id, citations)
                    data["citations"] = citations
            except Exception:  # noqa: BLE001
                # 历史回填失败不影响主流程
                pass
    return ApiResponse(data=data)


@router.delete("/history/{chat_id}", response_model=ApiResponse)
async def delete_chat_history(chat_id: str, container=Depends(get_container)):
    item = container.sqlite_repo.get_chat_log(chat_id)
    if not item:
        return ApiResponse(code=1004, message="chat history not found", data=None)
    container.sqlite_repo.delete_chat_log(chat_id)
    return ApiResponse(data={"id": chat_id, "deleted": True})


@router.delete("/history", response_model=ApiResponse)
async def clear_chat_history(container=Depends(get_container)):
    container.sqlite_repo.clear_chat_logs()
    return ApiResponse(data={"cleared": True})
