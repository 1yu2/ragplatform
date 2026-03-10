from __future__ import annotations

from fastapi import APIRouter, Depends

from app.container import get_container
from app.models.dto.common import ApiResponse

router = APIRouter(prefix="/settings", tags=["settings"])


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return f"****{value[-4:]}"


@router.get("/runtime", response_model=ApiResponse)
async def runtime_settings(container=Depends(get_container)):
    cfg = container.settings
    return ApiResponse(
        data={
            "env": cfg.app.env,
            "api_host": cfg.app.host,
            "api_port": cfg.app.port,
            "milvus": {
                "host": cfg.milvus.host,
                "port": cfg.milvus.port,
                "collection": cfg.milvus.collection,
                "collections": cfg.milvus.collections,
            },
            "minio": {
                "endpoint": cfg.minio.endpoint,
                "bucket": cfg.minio.bucket,
                "access_key": _mask_secret(cfg.minio.access_key),
                "use_presigned_url": cfg.minio.use_presigned_url,
                "presigned_expire_seconds": cfg.minio.presigned_expire_seconds,
            },
            "layout_api": {
                "url": cfg.layout_api.url,
                "fallback_url": cfg.layout_api.fallback_url,
                "token": _mask_secret(cfg.layout_api.token),
            },
            "embedding_api": {
                "url": cfg.embedding_api.url,
                "model_name": cfg.embedding_api.model_name,
                "auth_header": cfg.embedding_api.auth_header,
                "auth_scheme": cfg.embedding_api.auth_scheme,
                "api_key": _mask_secret(cfg.embedding_api.api_key),
            },
            "llm_api": {
                "url": cfg.llm_api.url,
                "model_name": cfg.llm_api.model_name,
                "api_key": _mask_secret(cfg.llm_api.api_key),
            },
        }
    )
