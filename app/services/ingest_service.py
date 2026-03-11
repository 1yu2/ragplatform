from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.dedup_service import DedupLogger, file_sha256


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass
class IngestResult:
    output_csv: str
    scanned_images: int
    written_rows: int
    skipped_rows: int
    duplicate_rows: int


class IngestService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.dedup_logger = DedupLogger(self.settings.dedup_log_path)

    @staticmethod
    def _iter_images(root: Path, limit: int | None = None) -> list[Path]:
        if not root.exists():
            return []
        files: list[Path] = []
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            files.append(p)
        files.sort(key=lambda x: str(x))
        if limit is not None and limit > 0:
            files = files[:limit]
        return files

    @staticmethod
    def _build_unique_id(path: Path, root: Path, used: set[str]) -> str:
        base = path.stem
        if base not in used:
            used.add(base)
            return base

        rel = path.relative_to(root).with_suffix("")
        prefixed = "_".join(rel.parts)
        if prefixed not in used:
            used.add(prefixed)
            return prefixed

        n = 2
        while True:
            candidate = f"{prefixed}_{n}"
            if candidate not in used:
                used.add(candidate)
                return candidate
            n += 1

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _read_sidecar_json(image_path: Path) -> dict[str, Any]:
        sidecar = image_path.with_suffix(".json")
        if not sidecar.exists():
            return {}
        try:
            with sidecar.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def ingest_bestseller_products(self, limit: int | None = None) -> IngestResult:
        root = Path(self.settings.data_bestseller_dir)
        images = self._iter_images(root, limit=limit)

        seen_sha: dict[str, str] = {}
        used_ids: set[str] = set()
        rows: list[dict[str, Any]] = []

        duplicate_rows = 0
        skipped_rows = 0

        for img in images:
            try:
                sha = file_sha256(img)
            except Exception:
                skipped_rows += 1
                self.dedup_logger.log(f"[ERROR] hash_failed path={img}")
                continue

            if sha in seen_sha:
                duplicate_rows += 1
                self.dedup_logger.log(
                    f"[DUP] keep={seen_sha[sha]} skip={img.resolve()} sha256={sha}"
                )
                continue

            product_id = self._build_unique_id(img, root, used_ids)
            seen_sha[sha] = product_id

            rows.append(
                {
                    "product_id": product_id,
                    "image_path": str(img.resolve()),
                    "category": "unknown",
                    "color": "unknown",
                    "style": "unknown",
                    "season": "unknown",
                    "sales_count": 0,
                    "description": "",
                    "price": 0,
                    "sha256": sha,
                }
            )

        output = Path(self.settings.data_products_csv_path)
        fields = [
            "product_id",
            "image_path",
            "category",
            "color",
            "style",
            "season",
            "sales_count",
            "description",
            "price",
            "sha256",
        ]
        self._write_csv(output, rows, fields)

        return IngestResult(
            output_csv=str(output),
            scanned_images=len(images),
            written_rows=len(rows),
            skipped_rows=skipped_rows,
            duplicate_rows=duplicate_rows,
        )

    def ingest_new_products(self, limit: int | None = None) -> IngestResult:
        root = Path(self.settings.data_new_dir)
        images = self._iter_images(root, limit=limit)

        used_ids: set[str] = set()
        rows: list[dict[str, Any]] = []
        skipped_rows = 0

        for img in images:
            new_id = self._build_unique_id(img, root, used_ids)
            meta = self._read_sidecar_json(img)

            category = (
                meta.get("CATEGORY")
                or meta.get("category")
                or "unknown"
            )
            style = meta.get("style") or "unknown"
            season = meta.get("season") or "unknown"

            if category == "unknown":
                prompt_hint = "Generate a clean e-commerce promotional image for this fashion item."
            else:
                prompt_hint = f"Generate a clean e-commerce promotional image for {str(category).lower()} products."

            rows.append(
                {
                    "new_id": new_id,
                    "image_path": str(img.resolve()),
                    "category": category,
                    "style": style,
                    "season": season,
                    "prompt_hint": prompt_hint,
                }
            )

        output = Path(self.settings.data_new_products_csv_path)
        fields = ["new_id", "image_path", "category", "style", "season", "prompt_hint"]
        self._write_csv(output, rows, fields)

        return IngestResult(
            output_csv=str(output),
            scanned_images=len(images),
            written_rows=len(rows),
            skipped_rows=skipped_rows,
            duplicate_rows=0,
        )
