from __future__ import annotations

import csv
from pathlib import Path

from app.core.config import get_settings


class CatalogService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _csv_path(self) -> Path:
        return Path(self.settings.data_new_products_csv_path)

    def get_new_product_by_id(self, new_id: str) -> dict | None:
        path = self._csv_path()
        if not path.exists():
            return None

        with path.open("r", encoding="utf-8", newline="") as f:
            rows = csv.DictReader(f)
            for row in rows:
                if (row.get("new_id") or "") == new_id:
                    image_path = row.get("image_path", "")
                    return {
                        "new_id": row.get("new_id", ""),
                        "image_path": image_path,
                        "category": row.get("category", "unknown"),
                        "style": row.get("style", "unknown"),
                        "season": row.get("season", "unknown"),
                        "prompt_hint": row.get("prompt_hint", ""),
                    }
        return None

    def list_new_products(self, limit: int = 100) -> list[dict]:
        path = self._csv_path()
        if not path.exists():
            return []

        out: list[dict] = []
        with path.open("r", encoding="utf-8", newline="") as f:
            rows = csv.DictReader(f)
            for row in rows:
                out.append(
                    {
                        "new_id": row.get("new_id", ""),
                        "image_path": row.get("image_path", ""),
                        "category": row.get("category", "unknown"),
                        "style": row.get("style", "unknown"),
                        "season": row.get("season", "unknown"),
                        "prompt_hint": row.get("prompt_hint", ""),
                    }
                )
                if len(out) >= limit:
                    break
        return out
