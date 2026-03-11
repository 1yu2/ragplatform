from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query

from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/new-products")
def list_new_products(limit: int = Query(default=100, ge=1, le=5000)) -> dict:
    svc = CatalogService()
    rows = svc.list_new_products(limit=limit)
    items = []
    for row in rows:
        image_path = row.get("image_path", "")
        row["preview_url"] = f"/api/assets/local-image?path={quote(image_path)}"
        items.append(row)
    return {"count": len(items), "items": items}


@router.get("/new-products/{new_id}")
def get_new_product(new_id: str) -> dict:
    svc = CatalogService()
    row = svc.get_new_product_by_id(new_id)
    if not row:
        raise HTTPException(status_code=404, detail="new product not found")

    image_path = row.get("image_path", "")
    row["preview_url"] = f"/api/assets/local-image?path={quote(image_path)}"
    return row
