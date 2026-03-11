from fastapi import APIRouter, Query

from app.services.milvus_service import MilvusService

router = APIRouter(prefix="/api/ingest/milvus", tags=["milvus"])


@router.post("/init")
def init_milvus_collection() -> dict:
    service = MilvusService()
    result = service.init_collection()
    return {
        "ok": result.ok,
        "host": result.host,
        "port": result.port,
        "collection": result.collection,
        "message": result.message,
    }


@router.post("/products")
def upsert_products_to_milvus(
    limit: int = Query(default=1000, ge=1, le=100000),
    batch_size: int = Query(default=32, ge=1, le=256),
) -> dict:
    service = MilvusService()
    result = service.upsert_products_from_csv(limit=limit, batch_size=batch_size)
    return {
        "ok": result.ok,
        "collection": result.collection,
        "scanned_rows": result.scanned_rows,
        "skipped_rows": result.skipped_rows,
        "upserted_rows": result.upserted_rows,
        "failed_rows": result.failed_rows,
        "message": result.message,
    }
