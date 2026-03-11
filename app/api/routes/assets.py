from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.config import get_settings

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/local-image")
def local_image(path: str = Query(..., min_length=1)):
    settings = get_settings()
    p = Path(path).expanduser().resolve()

    allowed_roots = [
        Path(settings.data_new_dir).resolve(),
        Path(settings.data_bestseller_dir).resolve(),
        Path(settings.data_generated_dir).resolve(),
    ]

    if not any(p == root or root in p.parents for root in allowed_roots):
        raise HTTPException(status_code=403, detail="path not allowed")

    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="file not found")

    return FileResponse(p)
