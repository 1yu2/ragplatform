from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.assets import router as assets_router
from app.api.routes.catalog import router as catalog_router
from app.api.routes.gallery import router as gallery_router
from app.api.routes.generate import router as generate_router
from app.api.routes.ingest import router as ingest_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.milvus import router as milvus_router
from app.api.routes.search import router as search_router
from app.core.config import get_settings
from app.core.logger import setup_logging
from app.models.db_models import create_db_and_tables


settings = get_settings()
setup_logging()

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest_router)
app.include_router(milvus_router)
app.include_router(search_router)
app.include_router(catalog_router)
app.include_router(assets_router)
app.include_router(generate_router)
app.include_router(gallery_router)
app.include_router(metrics_router)


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


@app.get("/healthz")
def healthz() -> dict:
    return {
        "ok": True,
        "env": settings.app_env,
        "mock": settings.enable_mock,
    }
