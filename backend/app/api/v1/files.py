from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.container import get_container
from app.models.dto.common import ApiResponse
from app.utils.pdf_util import split_pdf_bytes

router = APIRouter(prefix="/files", tags=["files"])
logger = logging.getLogger(__name__)


class ChunkEditRequest(BaseModel):
    chunk_text: str = Field(min_length=1, max_length=20000)


def _safe_raw_preview(raw: dict) -> dict:
    if not isinstance(raw, dict):
        return {"raw_type": type(raw).__name__}
    result = raw.get("result", {})
    if not isinstance(result, dict):
        return {"top_keys": list(raw.keys())[:20], "result_type": type(result).__name__}
    layout_results = result.get("layoutParsingResults")
    first_page = layout_results[0] if isinstance(layout_results, list) and layout_results else {}
    preview = {
        "top_keys": list(raw.keys())[:20],
        "errorCode": raw.get("errorCode"),
        "errorMsg": raw.get("errorMsg"),
        "result_keys": list(result.keys())[:20],
        "layout_results_len": len(layout_results) if isinstance(layout_results, list) else None,
    }
    if isinstance(first_page, dict):
        pruned = first_page.get("prunedResult", {})
        parsing_list = pruned.get("parsing_res_list") if isinstance(pruned, dict) else None
        markdown_text = ""
        markdown = first_page.get("markdown")
        if isinstance(markdown, dict):
            markdown_text = str(markdown.get("text") or "")
        preview["first_page"] = {
            "keys": list(first_page.keys())[:20],
            "parsing_res_len": len(parsing_list) if isinstance(parsing_list, list) else None,
            "markdown_preview": markdown_text[:400],
        }
    return preview


@router.post("/upload", response_model=ApiResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    container=Depends(get_container),
):
    if not file.filename:
        logger.warning("upload rejected: missing file name")
        raise HTTPException(status_code=400, detail="missing file name")
    if not file.filename.lower().endswith(".pdf"):
        logger.warning("upload rejected: only pdf supported filename=%s", file.filename)
        raise HTTPException(status_code=400, detail="only pdf supported")

    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        logger.warning("upload rejected: file too large filename=%s size=%s", file.filename, len(content))
        raise HTTPException(status_code=400, detail="file too large")

    try:
        result = await container.file_service.upload_pdf(file.filename, content)
    except ValueError as exc:
        logger.warning("upload rejected: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("upload failed")
        raise HTTPException(status_code=500, detail=f"upload failed: {exc}") from exc
    if not result["deduplicated"]:
        background_tasks.add_task(container.ingestion_service.run_task, result["task_id"])

    return ApiResponse(data={"file_id": result["file_id"], "task_id": result["task_id"], "deduplicated": result["deduplicated"]})


@router.get("", response_model=ApiResponse)
async def list_files(
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int | None = Query(default=None, ge=0),
    container=Depends(get_container),
):
    # 兼容旧前端：不传分页参数时仍返回数组。
    if limit is None and offset is None:
        records = container.file_service.list_files()
        data = []
        for item in records:
            task = container.file_service.latest_task(item["id"])
            data.append({**item, "task": task})
        return ApiResponse(data=data)

    safe_limit = 20 if limit is None else limit
    safe_offset = 0 if offset is None else offset
    records = container.file_service.list_files(limit=safe_limit, offset=safe_offset)
    total = container.file_service.count_files()
    items = []
    for item in records:
        task = container.file_service.latest_task(item["id"])
        items.append({**item, "task": task})
    return ApiResponse(
        data={
            "items": items,
            "limit": safe_limit,
            "offset": safe_offset,
            "total": total,
        }
    )


@router.get("/{file_id}/preview", response_model=ApiResponse)
async def file_preview(file_id: str, container=Depends(get_container)):
    file_record = container.sqlite_repo.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="file not found")
    preview = container.file_service.get_preview(file_id)
    return ApiResponse(data={"file_id": file_id, **preview})


@router.post("/{file_id}/reprocess", response_model=ApiResponse)
async def reprocess_file(file_id: str, background_tasks: BackgroundTasks, container=Depends(get_container)):
    try:
        task_info = await container.file_service.reprocess(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    background_tasks.add_task(container.ingestion_service.run_task, task_info["task_id"])
    return ApiResponse(data={"file_id": file_id, "task_id": task_info["task_id"]})


@router.delete("/{file_id}", response_model=ApiResponse)
async def delete_file(file_id: str, container=Depends(get_container)):
    file_record = container.sqlite_repo.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="file not found")

    try:
        container.milvus_repo.delete_by_file_id(file_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("delete file failed on milvus file_id=%s", file_id)
        raise HTTPException(status_code=500, detail=f"milvus delete failed: {exc}") from exc

    try:
        container.minio_repo.remove_object(file_record["minio_object_key"])
    except Exception as exc:  # noqa: BLE001
        logger.exception("delete file failed on minio file_id=%s", file_id)
        raise HTTPException(status_code=500, detail=f"minio delete failed: {exc}") from exc

    try:
        container.sqlite_repo.delete_file_cascade(file_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("delete file failed on sqlite file_id=%s", file_id)
        raise HTTPException(status_code=500, detail=f"sqlite delete failed: {exc}") from exc

    return ApiResponse(data={"file_id": file_id, "deleted": True})


@router.patch("/{file_id}/chunks/{chunk_id}", response_model=ApiResponse)
async def edit_chunk(
    file_id: str,
    chunk_id: str,
    payload: ChunkEditRequest,
    container=Depends(get_container),
):
    file_record = container.sqlite_repo.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="file not found")

    chunk = container.sqlite_repo.get_chunk(chunk_id)
    if not chunk or chunk.get("file_id") != file_id:
        raise HTTPException(status_code=404, detail="chunk not found")

    new_text = payload.chunk_text.strip()
    if not new_text:
        raise HTTPException(status_code=400, detail="chunk_text is empty")

    metadata: dict = {}
    raw_meta = chunk.get("metadata_json")
    if isinstance(raw_meta, str) and raw_meta.strip():
        try:
            loaded = json.loads(raw_meta)
            if isinstance(loaded, dict):
                metadata = loaded
        except Exception:  # noqa: BLE001
            metadata = {}
    metadata["manual_edited"] = True
    metadata["edited_at"] = datetime.now(timezone.utc).isoformat()

    container.sqlite_repo.update_chunk_text(chunk_id=chunk_id, chunk_text=new_text, metadata=metadata)

    emb = await container.embedding_service.embed_texts([new_text])
    if not emb:
        raise HTTPException(status_code=500, detail="embedding failed: empty response")
    vec = emb[0] if isinstance(emb[0], dict) else {}
    dense = vec.get("embedding") or [0.0] * container.settings.embedding_api.dim
    sparse = vec.get("spare_embedding") or vec.get("sparse_embedding") or {}

    item = {
        "chunk_id": chunk_id,
        "file_id": file_id,
        "file_name": file_record["file_name"],
        "page": int(chunk.get("page") or 0),
        "paragraph_id": str(chunk.get("paragraph_id") or ""),
        "block_type": str(chunk.get("block_type") or "text"),
        "chunk_text": new_text,
        "dense_vector": dense,
        "sparse_vector": sparse,
    }

    container.milvus_repo.ensure_collection(
        dim=container.settings.embedding_api.dim,
        enable_sparse=container.settings.milvus.enable_sparse,
    )
    container.milvus_repo.delete_by_chunk_ids([chunk_id])
    container.milvus_repo.upsert_chunks([item])

    return ApiResponse(
        data={
            "file_id": file_id,
            "chunk_id": chunk_id,
            "updated": True,
            "page": item["page"],
            "block_type": item["block_type"],
        }
    )


@router.delete("/{file_id}/chunks/{chunk_id}", response_model=ApiResponse)
async def delete_chunk(
    file_id: str,
    chunk_id: str,
    container=Depends(get_container),
):
    file_record = container.sqlite_repo.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="file not found")
    chunk = container.sqlite_repo.get_chunk(chunk_id)
    if not chunk or chunk.get("file_id") != file_id:
        raise HTTPException(status_code=404, detail="chunk not found")

    container.milvus_repo.delete_by_chunk_ids([chunk_id])
    container.sqlite_repo.delete_chunk(chunk_id)
    return ApiResponse(data={"file_id": file_id, "chunk_id": chunk_id, "deleted": True})


@router.post("/{file_id}/layout-debug", response_model=ApiResponse)
async def layout_debug(
    file_id: str,
    use_presigned: bool | None = Query(default=None),
    lite: bool = Query(default=True),
    sample_pages: int = Query(default=3, ge=1, le=20),
    container=Depends(get_container),
):
    file_record = container.sqlite_repo.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="file not found")

    obj_key = file_record["minio_object_key"]
    use_signed = container.settings.minio.use_presigned_url if use_presigned is None else use_presigned
    if use_signed:
        file_url = container.minio_repo.presigned_get_url(
            obj_key,
            expires_seconds=container.settings.minio.presigned_expire_seconds,
        )
        url_mode = "presigned"
    else:
        file_url = container.minio_repo.object_url(obj_key)
        url_mode = "object"

    try:
        if lite:
            pdf_bytes = container.minio_repo.get_object_bytes(obj_key)
            chunks, total_pages = split_pdf_bytes(pdf_bytes, sample_pages)
            _, first_chunk = chunks[0]
            raw = await container.layout_client.parse_upload(file_record["file_name"], first_chunk)
        else:
            total_pages = None
            raw = await container.layout_client.parse(file_url)
    except Exception as exc:  # noqa: BLE001
        return ApiResponse(
            code=1002,
            message="layout debug failed",
            data={
                "file_id": file_id,
                "url_mode": url_mode,
                "lite": lite,
                "sample_pages": sample_pages,
                "file_url": file_url,
                "error": str(exc),
            },
        )

    result = raw.get("result", {}) if isinstance(raw, dict) else {}
    data_info = result.get("dataInfo", {}) if isinstance(result, dict) else {}
    layout_results = result.get("layoutParsingResults", []) if isinstance(result, dict) else []
    normalized = container.parsing_service.normalize_layout_result(raw if isinstance(raw, dict) else {})
    normalized_pages = sorted({int(b.get("page", 1)) for b in normalized})

    return ApiResponse(
        data={
            "file_id": file_id,
            "url_mode": url_mode,
            "lite": lite,
            "sample_pages": sample_pages,
            "estimated_total_pages": total_pages if lite else None,
            "file_url": file_url,
            "top_keys": list(raw.keys())[:20] if isinstance(raw, dict) else [],
            "errorCode": raw.get("errorCode") if isinstance(raw, dict) else None,
            "errorMsg": raw.get("errorMsg") if isinstance(raw, dict) else None,
            "dataInfo": data_info,
            "layout_results_len": len(layout_results) if isinstance(layout_results, list) else None,
            "normalized_blocks": len(normalized),
            "normalized_pages": normalized_pages,
            "normalized_pages_len": len(normalized_pages),
            "raw_preview": _safe_raw_preview(raw if isinstance(raw, dict) else {}),
        }
    )
