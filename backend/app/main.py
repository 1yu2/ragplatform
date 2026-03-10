from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.container import get_container, init_runtime
from app.core.exceptions import AppError
from app.core.logging import setup_logging
from app.models.dto.common import ApiResponse

setup_logging()
container = get_container()

app = FastAPI(title="rag_sth", version="0.1.0")
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=container.settings.cors.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    init_runtime(container)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(status_code=400, content=ApiResponse(code=exc.code, message=exc.message, data=None).model_dump())


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
