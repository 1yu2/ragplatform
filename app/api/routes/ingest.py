import csv
from pathlib import Path

from fastapi import APIRouter, Query

from app.core.config import get_settings
from app.models.schemas import IngestResponse, IngestStatusResponse
from app.services.ingest_service import IngestService
from app.services.milvus_service import MilvusService

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/products", response_model=IngestResponse)
def ingest_products(limit: int = Query(default=1000, ge=1, le=100000)) -> IngestResponse:
    service = IngestService()
    result = service.ingest_bestseller_products(limit=limit)
    return IngestResponse(
        output_csv=result.output_csv,
        scanned_images=result.scanned_images,
        written_rows=result.written_rows,
        skipped_rows=result.skipped_rows,
        duplicate_rows=result.duplicate_rows,
    )


@router.post("/new-products", response_model=IngestResponse)
def ingest_new_products(limit: int = Query(default=1000, ge=1, le=100000)) -> IngestResponse:
    service = IngestService()
    result = service.ingest_new_products(limit=limit)
    return IngestResponse(
        output_csv=result.output_csv,
        scanned_images=result.scanned_images,
        written_rows=result.written_rows,
        skipped_rows=result.skipped_rows,
        duplicate_rows=result.duplicate_rows,
    )


@router.get("/status", response_model=IngestStatusResponse)
def ingest_status() -> IngestStatusResponse:
    settings = get_settings()
    products_rows = _csv_row_count(Path(settings.data_products_csv_path))
    new_products_rows = _csv_row_count(Path(settings.data_new_products_csv_path))

    milvus_status = MilvusService().get_collection_status()
    milvus_ready = milvus_status.ok and milvus_status.exists and milvus_status.entity_count > 0
    ready = products_rows > 0 and new_products_rows > 0 and milvus_ready

    return IngestStatusResponse(
        products_csv_rows=products_rows,
        new_products_csv_rows=new_products_rows,
        milvus_collection_exists=bool(milvus_status.exists),
        milvus_entity_count=int(milvus_status.entity_count),
        ready=ready,
    )


def _csv_row_count(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            return sum(1 for _ in csv.DictReader(f))
    except Exception:
        return 0
