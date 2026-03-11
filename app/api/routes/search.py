from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Query

from app.services.search_service import SearchService

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/by-new-id")
def search_by_new_id(new_id: str, top_k: int = Query(default=3, ge=1, le=50)) -> dict:
    service = SearchService()
    items = service.search_topk_by_new_id(new_id=new_id, top_k=top_k)
    return {
        "new_id": new_id,
        "top_k": top_k,
        "count": len(items),
        "items": [
            {
                "product_id": x.product_id,
                "image_path": x.image_path,
                "preview_url": f"/api/assets/local-image?path={quote(x.image_path)}",
                "final_score": x.final_score,
                "dense_score": x.dense_score,
                "sparse_score": x.sparse_score,
                "category": x.category,
                "style": x.style,
                "season": x.season,
                "sales_count": x.sales_count,
                "description": x.description,
            }
            for x in items
        ],
    }
