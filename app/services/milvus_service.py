from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.embedding_payloads import image_embedding_payload_candidates
from app.services.openai_compat_client import OpenAICompatClient


@dataclass
class MilvusInitResult:
    ok: bool
    host: str
    port: int
    collection: str
    message: str


@dataclass
class MilvusUpsertResult:
    ok: bool
    collection: str
    scanned_rows: int
    skipped_rows: int
    upserted_rows: int
    failed_rows: int
    message: str


@dataclass
class MilvusCollectionStatus:
    ok: bool
    collection: str
    exists: bool
    entity_count: int
    message: str


class MilvusService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.ai_client = OpenAICompatClient()
        self.embedding_pipeline_version = "image_v1"

    def init_collection(self) -> MilvusInitResult:
        try:
            from pymilvus import (
                Collection,
                CollectionSchema,
                DataType,
                FieldSchema,
                connections,
                utility,
            )
        except Exception as e:
            return MilvusInitResult(
                ok=False,
                host=self.settings.milvus_host,
                port=self.settings.milvus_port,
                collection=self.settings.milvus_collection,
                message=f"pymilvus import failed: {type(e).__name__}: {e}",
            )

        try:
            connections.connect(
                alias="default",
                host=self.settings.milvus_host,
                port=self.settings.milvus_port,
            )

            name = self.settings.milvus_collection
            dim = self.settings.vector_dim

            if utility.has_collection(name):
                col = Collection(name)
                if not col.has_index():
                    col.create_index(
                        field_name="image_vector",
                        index_params={
                            "index_type": "HNSW",
                            "metric_type": "COSINE",
                            "params": {"M": 16, "efConstruction": 200},
                        },
                    )
                col.load()
                return MilvusInitResult(
                    ok=True,
                    host=self.settings.milvus_host,
                    port=self.settings.milvus_port,
                    collection=name,
                    message="collection exists; index verified",
                )

            fields = [
                FieldSchema(name="product_id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
                FieldSchema(name="image_vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="color", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="style", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="season", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="sales_count", dtype=DataType.INT64),
                FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=2048),
                FieldSchema(name="price", dtype=DataType.FLOAT),
                FieldSchema(name="sha256", dtype=DataType.VARCHAR, max_length=128),
            ]
            schema = CollectionSchema(fields=fields, description="image generation MVP products")
            col = Collection(name=name, schema=schema)
            col.create_index(
                field_name="image_vector",
                index_params={
                    "index_type": "HNSW",
                    "metric_type": "COSINE",
                    "params": {"M": 16, "efConstruction": 200},
                },
            )
            col.load()

            return MilvusInitResult(
                ok=True,
                host=self.settings.milvus_host,
                port=self.settings.milvus_port,
                collection=name,
                message="collection created with HNSW index",
            )
        except Exception as e:
            return MilvusInitResult(
                ok=False,
                host=self.settings.milvus_host,
                port=self.settings.milvus_port,
                collection=self.settings.milvus_collection,
                message=f"milvus init failed: {type(e).__name__}: {e}",
            )

    def get_collection_status(self) -> MilvusCollectionStatus:
        try:
            from pymilvus import Collection, connections, utility

            connections.connect(
                alias="default",
                host=self.settings.milvus_host,
                port=self.settings.milvus_port,
            )
            name = self.settings.milvus_collection
            if not utility.has_collection(name):
                return MilvusCollectionStatus(
                    ok=True,
                    collection=name,
                    exists=False,
                    entity_count=0,
                    message="collection not found",
                )
            col = Collection(name)
            col.load()
            count = int(getattr(col, "num_entities", 0) or 0)
            return MilvusCollectionStatus(
                ok=True,
                collection=name,
                exists=True,
                entity_count=count,
                message="ok",
            )
        except Exception as e:
            return MilvusCollectionStatus(
                ok=False,
                collection=self.settings.milvus_collection,
                exists=False,
                entity_count=0,
                message=f"milvus status failed: {type(e).__name__}: {e}",
            )

    def upsert_products_from_csv(self, limit: int = 1000, batch_size: int = 32) -> MilvusUpsertResult:
        init_result = self.init_collection()
        if not init_result.ok:
            return MilvusUpsertResult(
                ok=False,
                collection=self.settings.milvus_collection,
                scanned_rows=0,
                skipped_rows=0,
                upserted_rows=0,
                failed_rows=0,
                message=f"init failed: {init_result.message}",
            )

        rows = self._read_products_csv(limit=limit)
        if not rows:
            return MilvusUpsertResult(
                ok=False,
                collection=self.settings.milvus_collection,
                scanned_rows=0,
                skipped_rows=0,
                upserted_rows=0,
                failed_rows=0,
                message="products.csv is empty",
            )

        existing_sha_map = self._existing_sha256_map([str(r.get("product_id", "")) for r in rows])
        rows_to_upsert: list[dict[str, str]] = []
        skipped_rows = 0
        force_full_upsert = self._needs_rebuild_for_embedding_version()
        for row in rows:
            pid = str(row.get("product_id", "") or "")
            sha = str(row.get("sha256", "") or "")
            if (not force_full_upsert) and pid and existing_sha_map.get(pid) == sha:
                skipped_rows += 1
                continue
            rows_to_upsert.append(row)

        if not rows_to_upsert:
            return MilvusUpsertResult(
                ok=True,
                collection=self.settings.milvus_collection,
                scanned_rows=len(rows),
                skipped_rows=skipped_rows,
                upserted_rows=0,
                failed_rows=0,
                message="no changed rows, skipped all",
            )

        try:
            vectors = self._embed_images(rows_to_upsert, batch_size=batch_size)
            self._upsert_rows(rows=rows_to_upsert, vectors=vectors)
            self._write_embedding_version_marker()
            msg = "upsert success"
            if force_full_upsert:
                msg = "upsert success (embedding version changed, rebuilt vectors)"
            return MilvusUpsertResult(
                ok=True,
                collection=self.settings.milvus_collection,
                scanned_rows=len(rows),
                skipped_rows=skipped_rows,
                upserted_rows=len(rows_to_upsert),
                failed_rows=0,
                message=msg,
            )
        except Exception as e:
            return MilvusUpsertResult(
                ok=False,
                collection=self.settings.milvus_collection,
                scanned_rows=len(rows),
                skipped_rows=skipped_rows,
                upserted_rows=0,
                failed_rows=len(rows_to_upsert),
                message=f"upsert failed: {type(e).__name__}: {e}",
            )

    def _existing_sha256_map(self, product_ids: list[str]) -> dict[str, str]:
        from pymilvus import Collection, connections

        ids = [x for x in product_ids if x]
        if not ids:
            return {}

        connections.connect(alias="default", host=self.settings.milvus_host, port=self.settings.milvus_port)
        col = Collection(self.settings.milvus_collection)
        col.load()

        out: dict[str, str] = {}
        for chunk in self._chunks(ids, 200):
            expr = f"product_id in [{','.join([self._quote_expr_value(x) for x in chunk])}]"
            rows = col.query(expr=expr, output_fields=["product_id", "sha256"])
            for row in rows or []:
                pid = str(row.get("product_id", "") or "")
                if not pid:
                    continue
                out[pid] = str(row.get("sha256", "") or "")
        return out

    def _upsert_rows(self, *, rows: list[dict[str, str]], vectors: list[list[float]]) -> None:
        from pymilvus import Collection, connections

        if len(rows) != len(vectors):
            raise RuntimeError(f"rows/vectors length mismatch: {len(rows)} != {len(vectors)}")

        connections.connect(alias="default", host=self.settings.milvus_host, port=self.settings.milvus_port)
        col = Collection(self.settings.milvus_collection)

        data = [
            [self._clip_str(r.get("product_id", ""), 128) for r in rows],
            vectors,
            [self._clip_str(r.get("category", "unknown"), 128) for r in rows],
            [self._clip_str(r.get("color", "unknown"), 64) for r in rows],
            [self._clip_str(r.get("style", "unknown"), 128) for r in rows],
            [self._clip_str(r.get("season", "unknown"), 64) for r in rows],
            [self._safe_int(r.get("sales_count"), 0) for r in rows],
            [self._clip_str(r.get("description", ""), 2048) for r in rows],
            [self._safe_float(r.get("price"), 0.0) for r in rows],
            [self._clip_str(r.get("sha256", ""), 128) for r in rows],
        ]

        if hasattr(col, "upsert"):
            col.upsert(data=data)
        else:
            product_ids = data[0]
            for chunk in self._chunks(product_ids, 200):
                expr_vals = ",".join([f'"{x}"' for x in chunk])
                col.delete(expr=f"product_id in [{expr_vals}]")
            col.insert(data=data)

        col.flush()
        col.load()

    def _embed_images(self, rows: list[dict[str, str]], batch_size: int = 32) -> list[list[float]]:
        if not self.settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is empty")

        all_vecs: list[list[float]] = []
        for row_batch in self._chunks(rows, max(1, batch_size)):
            image_paths = [str(r.get("image_path", "") or "") for r in row_batch]
            if any(not p for p in image_paths):
                raise RuntimeError("image_path is empty in products.csv")

            data: list[Any] | None = None
            last_err: Exception | None = None
            for payload in image_embedding_payload_candidates(image_paths):
                try:
                    resp = self.ai_client.embedding_openrouter(
                        input_data=payload,
                        model=self.settings.openrouter_embedding_model,
                    )
                    data = self._embedding_data(resp)
                    break
                except Exception as e:
                    last_err = e
                    continue

            if data is None:
                if last_err is None:
                    raise RuntimeError("embedding failed: no payload candidate succeeded")
                raise RuntimeError(f"embedding failed: {type(last_err).__name__}: {last_err}")

            batch_vecs: list[list[float] | None] = [None] * len(row_batch)
            for i, item in enumerate(data):
                idx = self._safe_int(self._get_attr(item, "index", i), i)
                if idx < 0 or idx >= len(row_batch):
                    continue
                emb = self._get_attr(item, "embedding", None)
                if emb is None:
                    raise RuntimeError("embedding item missing vector")
                batch_vecs[idx] = self._fit_vector(emb)

            for vec in batch_vecs:
                if vec is None:
                    raise RuntimeError("embedding response index mismatch")
                all_vecs.append(vec)

        return all_vecs

    @staticmethod
    def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _embedding_data(self, response: Any) -> list[Any]:
        if isinstance(response, dict):
            data = response.get("data")
        else:
            data = getattr(response, "data", None)
        if not isinstance(data, list) or not data:
            raise RuntimeError("invalid embedding response")
        return data

    def _fit_vector(self, vec: Any) -> list[float]:
        if not isinstance(vec, list):
            raise RuntimeError("embedding vector is not list")
        out = [float(x) for x in vec]
        dim = self.settings.vector_dim
        if len(out) == dim:
            return out
        if len(out) > dim:
            return out[:dim]
        return out + [0.0] * (dim - len(out))

    def _read_products_csv(self, limit: int) -> list[dict[str, str]]:
        path = Path(self.settings.data_products_csv_path)
        if not path.exists():
            return []

        rows: list[dict[str, str]] = []
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
                if limit > 0 and len(rows) >= limit:
                    break
        return rows

    @staticmethod
    def _safe_int(v: Any, default: int = 0) -> int:
        try:
            return int(v)
        except Exception:
            return default

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            return float(v)
        except Exception:
            return default

    @staticmethod
    def _clip_str(v: Any, max_len: int) -> str:
        s = str(v or "")
        if len(s) <= max_len:
            return s
        return s[:max_len]

    @staticmethod
    def _quote_expr_value(v: str) -> str:
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _embedding_version_marker_path(self) -> Path:
        return Path(self.settings.data_products_csv_path).resolve().parent / "milvus_embedding.version"

    def _embedding_version_value(self) -> str:
        return f"{self.embedding_pipeline_version}|{self.settings.openrouter_embedding_model}|dim={self.settings.vector_dim}"

    def _needs_rebuild_for_embedding_version(self) -> bool:
        marker = self._embedding_version_marker_path()
        current = self._embedding_version_value()
        if not marker.exists():
            return True
        try:
            previous = marker.read_text(encoding="utf-8").strip()
        except Exception:
            return True
        return previous != current

    def _write_embedding_version_marker(self) -> None:
        marker = self._embedding_version_marker_path()
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(self._embedding_version_value(), encoding="utf-8")

    @staticmethod
    def _chunks(items: list[Any], n: int):
        for i in range(0, len(items), n):
            yield items[i : i + n]
