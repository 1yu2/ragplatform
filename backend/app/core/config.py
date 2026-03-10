from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    name: str = "rag_sth"
    env: str = "local"
    host: str = "0.0.0.0"
    port: int = 8000
    first_token_timeout_sec: int = 10


class SqliteConfig(BaseModel):
    path: str = "./data/app.db"


class MilvusConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 19530
    collection: str = "rag_chunks"
    collections: list[str] = Field(default_factory=list)
    enable_sparse: bool = True
    chunk_text_max_length: int = 16384


class MinioConfig(BaseModel):
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str = "rag_sth"
    secure: bool = False
    use_presigned_url: bool = True
    presigned_expire_seconds: int = 1200


class LayoutApiConfig(BaseModel):
    url: str
    token: str = ""
    fallback_url: str = ""
    file_type: int = 0
    max_num_imgs: int = 512
    timeout_sec: int = 300


class EmbeddingApiConfig(BaseModel):
    url: str
    model_name: str = "bge-m3"
    dim: int = 1024
    api_key: str = ""
    auth_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    timeout_sec: int = 300
    batch_size: int = 64
    max_retries: int = 3
    retry_backoff_sec: float = 2.0


class LlmApiConfig(BaseModel):
    url: str
    api_key: str = ""
    model_name: str = "deepseek-chat"
    max_tokens: int = 131072
    stream: bool = True


class RetrievalConfig(BaseModel):
    top_k: int = 5
    dense_weight: float = 0.7
    bm25_weight: float = 0.3
    refuse_threshold: float = 0.1


class ChunkingConfig(BaseModel):
    chunk_size: int = 2800
    overlap: int = 80
    min_chunk_chars: int = 600
    long_question_threshold: int = 35


class IngestionConfig(BaseModel):
    enforce_page_coverage: bool = True
    min_total_pages_to_enforce: int = 5
    min_parsed_pages: int = 2
    min_page_coverage_ratio: float = 0.2
    enable_slice_fallback: bool = True
    slice_pages: int = 3
    parse_batch_pages: int = 512
    min_parse_batch_pages: int = 1
    skip_failed_pages: bool = True
    max_concurrent_tasks: int = 1


class CorsConfig(BaseModel):
    allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


class Settings(BaseModel):
    app: AppConfig
    sqlite: SqliteConfig
    milvus: MilvusConfig
    minio: MinioConfig
    layout_api: LayoutApiConfig
    embedding_api: EmbeddingApiConfig
    llm_api: LlmApiConfig
    retrieval: RetrievalConfig
    chunking: ChunkingConfig
    ingestion: IngestionConfig
    cors: CorsConfig


def _deep_update(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_update(result[key], value)
        else:
            result[key] = value
    return result


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    data = dict(data)

    def set_path(path: list[str], value: Any) -> None:
        current = data
        for key in path[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[path[-1]] = value

    env_map: dict[str, tuple[list[str], Any]] = {
        "APP_ENV": (["app", "env"], str),
        "API_HOST": (["app", "host"], str),
        "API_PORT": (["app", "port"], int),
        "SQLITE_PATH": (["sqlite", "path"], str),
        "MILVUS_HOST": (["milvus", "host"], str),
        "MILVUS_PORT": (["milvus", "port"], int),
        "MILVUS_COLLECTION": (["milvus", "collection"], str),
        "MILVUS_COLLECTIONS": (["milvus", "collections"], lambda v: [x.strip() for x in str(v).split(",") if x.strip()]),
        "MILVUS_ENABLE_SPARSE": (["milvus", "enable_sparse"], lambda v: str(v).lower() == "true"),
        "MILVUS_CHUNK_TEXT_MAX_LENGTH": (["milvus", "chunk_text_max_length"], int),
        "MINIO_ENDPOINT": (["minio", "endpoint"], str),
        "MINIO_ACCESS_KEY": (["minio", "access_key"], str),
        "MINIO_SECRET_KEY": (["minio", "secret_key"], str),
        "MINIO_BUCKET": (["minio", "bucket"], str),
        "MINIO_SECURE": (["minio", "secure"], lambda v: str(v).lower() == "true"),
        "MINIO_USE_PRESIGNED_URL": (["minio", "use_presigned_url"], lambda v: str(v).lower() == "true"),
        "MINIO_PRESIGNED_EXPIRE_SECONDS": (["minio", "presigned_expire_seconds"], int),
        "LAYOUT_API_URL": (["layout_api", "url"], str),
        "LAYOUT_API_TOKEN": (["layout_api", "token"], str),
        "LAYOUT_API_FALLBACK_URL": (["layout_api", "fallback_url"], str),
        "LAYOUT_API_FILE_TYPE": (["layout_api", "file_type"], int),
        "LAYOUT_API_MAX_NUM_IMGS": (["layout_api", "max_num_imgs"], int),
        "LAYOUT_API_TIMEOUT_SEC": (["layout_api", "timeout_sec"], int),
        "EMBEDDING_API_URL": (["embedding_api", "url"], str),
        "EMBEDDING_MODEL_NAME": (["embedding_api", "model_name"], str),
        "EMBEDDING_API_KEY": (["embedding_api", "api_key"], str),
        "EMBEDDING_API_AUTH_HEADER": (["embedding_api", "auth_header"], str),
        "EMBEDDING_API_AUTH_SCHEME": (["embedding_api", "auth_scheme"], str),
        "EMBEDDING_API_TIMEOUT_SEC": (["embedding_api", "timeout_sec"], int),
        "EMBEDDING_BATCH_SIZE": (["embedding_api", "batch_size"], int),
        "EMBEDDING_MAX_RETRIES": (["embedding_api", "max_retries"], int),
        "EMBEDDING_RETRY_BACKOFF_SEC": (["embedding_api", "retry_backoff_sec"], float),
        "LLM_API_URL": (["llm_api", "url"], str),
        "LLM_API_KEY": (["llm_api", "api_key"], str),
        "LLM_MODEL_NAME": (["llm_api", "model_name"], str),
        "LLM_MAX_TOKENS": (["llm_api", "max_tokens"], int),
        "RETRIEVAL_TOP_K": (["retrieval", "top_k"], int),
        "RETRIEVAL_DENSE_WEIGHT": (["retrieval", "dense_weight"], float),
        "RETRIEVAL_BM25_WEIGHT": (["retrieval", "bm25_weight"], float),
        "RETRIEVAL_REFUSE_THRESHOLD": (["retrieval", "refuse_threshold"], float),
        "CHUNK_SIZE": (["chunking", "chunk_size"], int),
        "CHUNK_OVERLAP": (["chunking", "overlap"], int),
        "CHUNK_MIN_CHARS": (["chunking", "min_chunk_chars"], int),
        "CHUNK_LONG_QUESTION_THRESHOLD": (["chunking", "long_question_threshold"], int),
        "INGEST_ENFORCE_PAGE_COVERAGE": (["ingestion", "enforce_page_coverage"], lambda v: str(v).lower() == "true"),
        "INGEST_MIN_TOTAL_PAGES_TO_ENFORCE": (["ingestion", "min_total_pages_to_enforce"], int),
        "INGEST_MIN_PARSED_PAGES": (["ingestion", "min_parsed_pages"], int),
        "INGEST_MIN_PAGE_COVERAGE_RATIO": (["ingestion", "min_page_coverage_ratio"], float),
        "INGEST_ENABLE_SLICE_FALLBACK": (["ingestion", "enable_slice_fallback"], lambda v: str(v).lower() == "true"),
        "INGEST_SLICE_PAGES": (["ingestion", "slice_pages"], int),
        "INGEST_PARSE_BATCH_PAGES": (["ingestion", "parse_batch_pages"], int),
        "INGEST_MIN_PARSE_BATCH_PAGES": (["ingestion", "min_parse_batch_pages"], int),
        "INGEST_SKIP_FAILED_PAGES": (["ingestion", "skip_failed_pages"], lambda v: str(v).lower() == "true"),
        "INGEST_MAX_CONCURRENT_TASKS": (["ingestion", "max_concurrent_tasks"], int),
    }

    for env_name, (path, caster) in env_map.items():
        val = os.getenv(env_name)
        if val is not None and val != "":
            set_path(path, caster(val))

    cors = os.getenv("CORS_ALLOW_ORIGINS")
    if cors:
        set_path(["cors", "allow_origins"], [x.strip() for x in cors.split(",") if x.strip()])

    return data


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[2]
    config_dir = root / "config"
    _load_env_file(root / ".env")

    base_data = _read_yaml(config_dir / "base.yaml")
    env = os.getenv("APP_ENV") or base_data.get("app", {}).get("env", "local")
    env_data = _read_yaml(config_dir / f"{env}.yaml")

    merged = _deep_update(base_data, env_data)
    merged = _apply_env_overrides(merged)

    settings = Settings.model_validate(merged)

    # 兼容单 collection 配置，同时支持多 collection 自动初始化。
    if not settings.milvus.collections:
        settings.milvus.collections = [settings.milvus.collection]
    if settings.milvus.collection not in settings.milvus.collections:
        settings.milvus.collections.insert(0, settings.milvus.collection)
    settings.milvus.collection = settings.milvus.collections[0]

    db_path = Path(settings.sqlite.path)
    if not db_path.is_absolute():
        db_path = root / db_path
        settings.sqlite.path = str(db_path)

    return settings
