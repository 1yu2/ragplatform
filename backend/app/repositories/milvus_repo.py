from __future__ import annotations

import logging
from typing import Any

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

logger = logging.getLogger(__name__)


class MilvusRepo:
    def __init__(self, host: str, port: int, collection_name: str, chunk_text_max_length: int = 16384):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.chunk_text_max_length = max(1, int(chunk_text_max_length))
        self._effective_chunk_text_max_length = self.chunk_text_max_length
        self._connected = False

    def connect(self) -> None:
        if self._connected:
            return
        connections.connect(alias="default", host=self.host, port=str(self.port))
        self._connected = True

    def drop_collection(self) -> None:
        self.connect()
        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)

    def _indexed_fields(self, collection: Collection) -> set[str]:
        fields: set[str] = set()
        try:
            for idx in collection.indexes:
                field_name = getattr(idx, "field_name", None)
                if field_name:
                    fields.add(str(field_name))
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to inspect indexes: %s", exc)
        return fields

    def _ensure_dense_index(self, collection: Collection, indexed_fields: set[str]) -> None:
        if "dense_vector" not in indexed_fields:
            collection.create_index(
                field_name="dense_vector",
                index_params={"index_type": "IVF_FLAT", "metric_type": "IP", "params": {"nlist": 1024}},
            )

    def _ensure_sparse_index(self, collection: Collection, field_names: set[str], indexed_fields: set[str]) -> None:
        if "sparse_vector" not in field_names:
            return
        if "sparse_vector" in indexed_fields:
            return
        collection.create_index(
            field_name="sparse_vector",
            index_params={
                "index_type": "SPARSE_INVERTED_INDEX",
                "metric_type": "IP",
                "params": {"drop_ratio_build": 0.2},
            },
        )

    @staticmethod
    def _field_max_length(field: Any) -> int | None:
        try:
            val = getattr(field, "max_length", None)
            if isinstance(val, int) and val > 0:
                return val
            if isinstance(val, str) and val.strip().isdigit():
                parsed = int(val.strip())
                if parsed > 0:
                    return parsed
        except Exception:  # noqa: BLE001
            pass
        try:
            params = getattr(field, "params", None)
            if isinstance(params, dict):
                for key in ("max_length", "maxLength"):
                    v = params.get(key)
                    if isinstance(v, int) and v > 0:
                        return v
                    if isinstance(v, str) and v.isdigit() and int(v) > 0:
                        return int(v)
        except Exception:  # noqa: BLE001
            pass
        return None

    @staticmethod
    def _truncate_utf8_by_bytes(text: str, max_bytes: int) -> str:
        max_bytes = max(1, int(max_bytes))
        raw = str(text or "").encode("utf-8")
        if len(raw) <= max_bytes:
            return str(text or "")
        # 只可能在末尾截断半个 UTF-8 字符，ignore 即可安全丢弃不完整字节。
        return raw[:max_bytes].decode("utf-8", errors="ignore")

    def _sync_effective_chunk_text_max_length(self, collection: Collection) -> None:
        effective = self.chunk_text_max_length
        for field in collection.schema.fields:
            if str(getattr(field, "name", "")) != "chunk_text":
                continue
            field_limit = self._field_max_length(field)
            if isinstance(field_limit, int) and field_limit > 0:
                effective = field_limit
            break
        self._effective_chunk_text_max_length = max(1, int(effective))
        if self._effective_chunk_text_max_length < self.chunk_text_max_length:
            logger.warning(
                "collection=%s chunk_text max_length=%s (configured=%s). "
                "To truly increase storage length, recreate collection.",
                self.collection_name,
                self._effective_chunk_text_max_length,
                self.chunk_text_max_length,
            )

    def ensure_collection(self, dim: int = 1024, enable_sparse: bool = True) -> None:
        self.connect()
        if not utility.has_collection(self.collection_name):
            fields = [
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, is_primary=True, auto_id=False, max_length=64),
                FieldSchema(name="file_id", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="file_name", dtype=DataType.VARCHAR, max_length=255),
                FieldSchema(name="page", dtype=DataType.INT64),
                FieldSchema(name="paragraph_id", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="block_type", dtype=DataType.VARCHAR, max_length=32),
                FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=self.chunk_text_max_length),
                FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
            ]

            if enable_sparse:
                try:
                    fields.append(FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR))
                except AttributeError:
                    logger.warning("Milvus SDK does not expose SPARSE_FLOAT_VECTOR, continue with dense only")

            schema = CollectionSchema(fields=fields, description="RAG chunks")
            Collection(self.collection_name, schema=schema)

        collection = Collection(self.collection_name)
        self._sync_effective_chunk_text_max_length(collection)
        field_names = {f.name for f in collection.schema.fields}
        indexed_fields = self._indexed_fields(collection)

        self._ensure_dense_index(collection, indexed_fields)
        indexed_fields = self._indexed_fields(collection)
        self._ensure_sparse_index(collection, field_names, indexed_fields)
        collection.load()

    def upsert_chunks(self, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        self.connect()
        collection = Collection(self.collection_name)
        self._sync_effective_chunk_text_max_length(collection)

        chunk_ids = [x["chunk_id"] for x in items]
        file_ids = [x["file_id"] for x in items]
        file_names = [x["file_name"] for x in items]
        pages = [x.get("page", 0) for x in items]
        paragraph_ids = [x.get("paragraph_id", "") for x in items]
        block_types = [x.get("block_type", "text") for x in items]
        max_len = max(1, int(self._effective_chunk_text_max_length))
        texts: list[str] = []
        truncated = 0
        max_seen_bytes = 0
        for x in items:
            raw_text = str(x.get("chunk_text", "") or "")
            raw_bytes = len(raw_text.encode("utf-8"))
            max_seen_bytes = max(max_seen_bytes, raw_bytes)
            safe_text = self._truncate_utf8_by_bytes(raw_text, max_len)
            if len(safe_text.encode("utf-8")) < raw_bytes:
                truncated += 1
            texts.append(safe_text)
        if truncated > 0:
            logger.warning(
                "collection=%s chunk_text truncated rows=%s/%s max_allowed_bytes=%s max_seen_bytes=%s",
                self.collection_name,
                truncated,
                len(items),
                max_len,
                max_seen_bytes,
            )
        dense_vecs = [x["dense_vector"] for x in items]

        data = [chunk_ids, file_ids, file_names, pages, paragraph_ids, block_types, texts, dense_vecs]

        field_names = {f.name for f in collection.schema.fields}
        if "sparse_vector" in field_names:
            sparse_vecs = [x.get("sparse_vector", {}) for x in items]
            data.append(sparse_vecs)

        collection.insert(data)
        collection.flush()

    def delete_by_file_id(self, file_id: str) -> None:
        if not file_id:
            return
        self.connect()
        if not utility.has_collection(self.collection_name):
            return
        collection = Collection(self.collection_name)
        collection.load()
        safe_file_id = str(file_id).replace("\\", "\\\\").replace('"', '\\"')
        collection.delete(expr=f'file_id == "{safe_file_id}"')
        collection.flush()

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        valid_ids = [str(x) for x in chunk_ids if str(x).strip()]
        if not valid_ids:
            return
        self.connect()
        if not utility.has_collection(self.collection_name):
            return
        collection = Collection(self.collection_name)
        collection.load()
        escaped = [x.replace("\\", "\\\\").replace('"', '\\"') for x in valid_ids]
        joined = ", ".join([f'"{x}"' for x in escaped])
        collection.delete(expr=f"chunk_id in [{joined}]")
        collection.flush()

    def search_dense(self, query_vec: list[float], top_k: int) -> list[dict[str, Any]]:
        self.connect()
        if not utility.has_collection(self.collection_name):
            return []

        collection = Collection(self.collection_name)
        collection.load()
        search_res = collection.search(
            data=[query_vec],
            anns_field="dense_vector",
            param={"metric_type": "IP", "params": {"nprobe": 16}},
            limit=top_k,
            output_fields=["chunk_id", "file_id", "file_name", "page", "paragraph_id", "block_type", "chunk_text"],
        )

        output: list[dict[str, Any]] = []
        for hits in search_res:
            for hit in hits:
                entity = hit.entity
                output.append(
                    {
                        "chunk_id": entity.get("chunk_id"),
                        "file_id": entity.get("file_id"),
                        "file_name": entity.get("file_name"),
                        "page": entity.get("page"),
                        "paragraph_id": entity.get("paragraph_id"),
                        "block_type": entity.get("block_type"),
                        "chunk_text": entity.get("chunk_text"),
                        "dense_score": float(hit.score),
                    }
                )
        return output
