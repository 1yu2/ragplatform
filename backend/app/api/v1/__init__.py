from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.evaluation import router as evaluation_router
from app.api.v1.files import router as files_router
from app.api.v1.settings import router as settings_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(files_router)
api_router.include_router(chat_router)
api_router.include_router(evaluation_router)
api_router.include_router(settings_router)
