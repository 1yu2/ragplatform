from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency in early bootstrap
    yaml = None


ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "config"


@dataclass
class Settings:
    app_env: str
    app_name: str
    debug: bool
    host: str
    port: int

    sqlite_url: str

    enable_mock: bool

    openrouter_api_key: str
    modelscope_api_key: str

    modelscope_base_url: str
    openrouter_base_url: str
    modelscope_llm_model: str
    openrouter_embedding_model: str
    openrouter_image_model: str

    milvus_host: str
    milvus_port: int
    milvus_collection: str
    vector_dim: int

    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool
    minio_use_presigned_url: bool
    minio_presigned_expire_seconds: int

    data_bestseller_dir: str
    data_new_dir: str
    data_products_csv_path: str
    data_new_products_csv_path: str
    data_generated_dir: str
    logs_dir: str
    dedup_log_path: str

    retrieval_dense_weight: float
    retrieval_sparse_weight: float
    retrieval_top_k: int


def _read_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        return {}
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid config file format: {path}")
    return data


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = _deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


def _as_bool(value: str | bool | None, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _load_env_file(env: str) -> None:
    """Load .env.<env> (and .env fallback) without overriding existing process env vars."""
    candidates = [ROOT_DIR / f".env.{env}", ROOT_DIR / ".env"]
    for path in candidates:
        if not path.exists() or not path.is_file():
            continue

        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if not key or key in os.environ:
                    continue

                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]

                os.environ[key] = value


def _flatten(cfg: dict[str, Any], env: str) -> Settings:
    app = cfg.get("app", {})
    db = cfg.get("database", {})
    ai = cfg.get("ai", {})
    milvus = cfg.get("milvus", {})
    minio = cfg.get("minio", {})
    data = cfg.get("data", {})
    retrieval = cfg.get("retrieval", {})

    return Settings(
        app_env=env,
        app_name=str(app.get("name", "generate-image-mvp")),
        debug=_as_bool(app.get("debug", False), False),
        host=str(app.get("host", "0.0.0.0")),
        port=int(app.get("port", 8000)),
        sqlite_url=str(db.get("sqlite_url", "sqlite:///./data/app.db")),
        enable_mock=_as_bool(ai.get("enable_mock", True), True),
        openrouter_api_key=str(ai.get("openrouter_api_key", "")),
        modelscope_api_key=str(ai.get("modelscope_api_key", "")),
        modelscope_base_url=str(ai.get("modelscope_base_url", "https://api-inference.modelscope.cn/v1")),
        openrouter_base_url=str(ai.get("openrouter_base_url", "https://openrouter.ai/api/v1")),
        modelscope_llm_model=str(ai.get("modelscope_llm_model", "Qwen/Qwen3.5-397B-A17B")),
        openrouter_embedding_model=str(ai.get("openrouter_embedding_model", "jina-embeddings-v4")),
        openrouter_image_model=str(ai.get("openrouter_image_model", "google/gemini-3.1-flash-image-preview")),
        milvus_host=str(milvus.get("host", "127.0.0.1")),
        milvus_port=int(milvus.get("port", 19530)),
        milvus_collection=str(milvus.get("collection", "img_all")),
        vector_dim=int(milvus.get("vector_dim", 2048)),
        minio_endpoint=str(minio.get("endpoint", "127.0.0.1:9000")),
        minio_access_key=str(minio.get("access_key", "minioadmin")),
        minio_secret_key=str(minio.get("secret_key", "minioadmin")),
        minio_bucket=str(minio.get("bucket", "img-all")),
        minio_secure=_as_bool(minio.get("secure", False), False),
        minio_use_presigned_url=_as_bool(minio.get("use_presigned_url", True), True),
        minio_presigned_expire_seconds=int(minio.get("presigned_expire_seconds", 60)),
        data_bestseller_dir=str(data.get("bestseller_dir", "/Users/fishyuu/idea_project/mul_p2p/fashion_img")),
        data_new_dir=str(data.get("new_dir", "/Users/fishyuu/idea_project/mul_p2p/product")),
        data_products_csv_path=str(data.get("products_csv_path", str(ROOT_DIR / "data" / "products.csv"))),
        data_new_products_csv_path=str(data.get("new_products_csv_path", str(ROOT_DIR / "data" / "new_products.csv"))),
        data_generated_dir=str(data.get("generated_dir", str(ROOT_DIR / "data" / "generated"))),
        logs_dir=str(data.get("logs_dir", "/Users/fishyuu/idea_project/mul_p2p/generate_image/logs")),
        dedup_log_path=str(data.get("dedup_log_path", "/Users/fishyuu/idea_project/mul_p2p/generate_image/logs/debug.log")),
        retrieval_dense_weight=float(retrieval.get("dense_weight", 0.7)),
        retrieval_sparse_weight=float(retrieval.get("sparse_weight", 0.3)),
        retrieval_top_k=int(retrieval.get("top_k", 3)),
    )


def _apply_env_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "APP_NAME": ("app", "name"),
        "APP_DEBUG": ("app", "debug"),
        "APP_HOST": ("app", "host"),
        "APP_PORT": ("app", "port"),
        "SQLITE_URL": ("database", "sqlite_url"),
        "ENABLE_MOCK": ("ai", "enable_mock"),
        "OPENROUTER_API_KEY": ("ai", "openrouter_api_key"),
        "MODELSCOPE_API_KEY": ("ai", "modelscope_api_key"),
        "MODELSCOPE_BASE_URL": ("ai", "modelscope_base_url"),
        "OPENROUTER_BASE_URL": ("ai", "openrouter_base_url"),
        "MODELSCOPE_LLM_MODEL": ("ai", "modelscope_llm_model"),
        "OPENROUTER_EMBEDDING_MODEL": ("ai", "openrouter_embedding_model"),
        "OPENROUTER_IMAGE_MODEL": ("ai", "openrouter_image_model"),
        "MILVUS_HOST": ("milvus", "host"),
        "MILVUS_PORT": ("milvus", "port"),
        "MILVUS_COLLECTION": ("milvus", "collection"),
        "VECTOR_DIM": ("milvus", "vector_dim"),
        "MINIO_ENDPOINT": ("minio", "endpoint"),
        "MINIO_ACCESS_KEY": ("minio", "access_key"),
        "MINIO_SECRET_KEY": ("minio", "secret_key"),
        "MINIO_BUCKET": ("minio", "bucket"),
        "MINIO_SECURE": ("minio", "secure"),
        "MINIO_USE_PRESIGNED_URL": ("minio", "use_presigned_url"),
        "MINIO_PRESIGNED_EXPIRE_SECONDS": ("minio", "presigned_expire_seconds"),
        "DATA_BESTSELLER_DIR": ("data", "bestseller_dir"),
        "DATA_NEW_DIR": ("data", "new_dir"),
        "DATA_PRODUCTS_CSV_PATH": ("data", "products_csv_path"),
        "DATA_NEW_PRODUCTS_CSV_PATH": ("data", "new_products_csv_path"),
        "DATA_GENERATED_DIR": ("data", "generated_dir"),
        "LOGS_DIR": ("data", "logs_dir"),
        "DEDUP_LOG_PATH": ("data", "dedup_log_path"),
        "RETRIEVAL_DENSE_WEIGHT": ("retrieval", "dense_weight"),
        "RETRIEVAL_SPARSE_WEIGHT": ("retrieval", "sparse_weight"),
        "RETRIEVAL_TOP_K": ("retrieval", "top_k"),
    }

    out = dict(cfg)
    for env_key, path in mapping.items():
        value = os.getenv(env_key)
        if value is None:
            continue
        p0, p1 = path
        section = dict(out.get(p0, {}))
        section[p1] = value
        out[p0] = section
    return out


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    env = os.getenv("APP_ENV", "local").strip().lower() or "local"
    _load_env_file(env)
    base_cfg = _read_yaml(CONFIG_DIR / "base.yaml")
    env_cfg = _read_yaml(CONFIG_DIR / f"{env}.yaml")
    merged = _deep_merge(base_cfg, env_cfg)
    merged = _apply_env_overrides(merged)
    return _flatten(merged, env)
