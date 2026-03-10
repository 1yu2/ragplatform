from __future__ import annotations

import logging
from dataclasses import dataclass

from app.clients.embedding_client import EmbeddingClient
from app.clients.layout_client import LayoutClient
from app.clients.llm_client import LlmClient
from app.core.config import Settings, get_settings
from app.repositories.milvus_repo import MilvusRepo
from app.repositories.minio_repo import MinioRepo
from app.repositories.sqlite_repo import SqliteRepo
from app.services.chat_service import ChatService
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.evaluation_service import EvaluationService
from app.services.file_service import FileService
from app.services.ingestion_service import IngestionService
from app.services.parsing_service import ParsingService
from app.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    sqlite_repo: SqliteRepo
    minio_repo: MinioRepo
    milvus_repo: MilvusRepo

    layout_client: LayoutClient
    embedding_client: EmbeddingClient
    llm_client: LlmClient

    parsing_service: ParsingService
    chunking_service: ChunkingService
    embedding_service: EmbeddingService
    ingestion_service: IngestionService
    retrieval_service: RetrievalService
    chat_service: ChatService
    file_service: FileService
    evaluation_service: EvaluationService


_container: Container | None = None


def _build_container() -> Container:
    settings = get_settings()

    sqlite_repo = SqliteRepo(settings.sqlite.path)
    minio_repo = MinioRepo(
        endpoint=settings.minio.endpoint,
        access_key=settings.minio.access_key,
        secret_key=settings.minio.secret_key,
        bucket=settings.minio.bucket,
        secure=settings.minio.secure,
    )
    milvus_repo = MilvusRepo(
        host=settings.milvus.host,
        port=settings.milvus.port,
        collection_name=settings.milvus.collection,
        chunk_text_max_length=settings.milvus.chunk_text_max_length,
    )

    layout_client = LayoutClient(
        url=settings.layout_api.url,
        token=settings.layout_api.token,
        fallback_url=settings.layout_api.fallback_url,
        file_type=settings.layout_api.file_type,
        max_num_imgs=settings.layout_api.max_num_imgs,
        timeout_sec=settings.layout_api.timeout_sec,
    )
    embedding_client = EmbeddingClient(
        url=settings.embedding_api.url,
        model_name=settings.embedding_api.model_name,
        api_key=settings.embedding_api.api_key,
        auth_header=settings.embedding_api.auth_header,
        auth_scheme=settings.embedding_api.auth_scheme,
        timeout_sec=settings.embedding_api.timeout_sec,
    )
    llm_client = LlmClient(
        url=settings.llm_api.url,
        api_key=settings.llm_api.api_key,
        model_name=settings.llm_api.model_name,
        max_tokens=settings.llm_api.max_tokens,
    )

    parsing_service = ParsingService()
    chunking_service = ChunkingService(
        chunk_size=settings.chunking.chunk_size,
        overlap=settings.chunking.overlap,
        min_chunk_chars=settings.chunking.min_chunk_chars,
    )
    embedding_service = EmbeddingService(
        client=embedding_client,
        batch_size=settings.embedding_api.batch_size,
        max_retries=settings.embedding_api.max_retries,
        retry_backoff_sec=settings.embedding_api.retry_backoff_sec,
    )

    ingestion_service = IngestionService(
        sqlite_repo=sqlite_repo,
        parsing_service=parsing_service,
        chunking_service=chunking_service,
        embedding_service=embedding_service,
        milvus_repo=milvus_repo,
        minio_repo=minio_repo,
        layout_client=layout_client,
        embedding_dim=settings.embedding_api.dim,
        enable_sparse=settings.milvus.enable_sparse,
        use_presigned_url=settings.minio.use_presigned_url,
        presigned_expire_seconds=settings.minio.presigned_expire_seconds,
        enforce_page_coverage=settings.ingestion.enforce_page_coverage,
        min_total_pages_to_enforce=settings.ingestion.min_total_pages_to_enforce,
        min_parsed_pages=settings.ingestion.min_parsed_pages,
        min_page_coverage_ratio=settings.ingestion.min_page_coverage_ratio,
        enable_slice_fallback=settings.ingestion.enable_slice_fallback,
        slice_pages=settings.ingestion.slice_pages,
        parse_batch_pages=settings.ingestion.parse_batch_pages,
        min_parse_batch_pages=settings.ingestion.min_parse_batch_pages,
        skip_failed_pages=settings.ingestion.skip_failed_pages,
        max_concurrent_tasks=settings.ingestion.max_concurrent_tasks,
    )

    retrieval_service = RetrievalService(
        embedding_service=embedding_service,
        milvus_repo=milvus_repo,
        sqlite_repo=sqlite_repo,
        top_k=settings.retrieval.top_k,
        dense_weight=settings.retrieval.dense_weight,
        bm25_weight=settings.retrieval.bm25_weight,
    )

    chat_service = ChatService(
        llm_client=llm_client,
        retrieval_service=retrieval_service,
        sqlite_repo=sqlite_repo,
        refuse_threshold=settings.retrieval.refuse_threshold,
        long_question_threshold=settings.chunking.long_question_threshold,
    )

    file_service = FileService(
        sqlite_repo=sqlite_repo,
        minio_repo=minio_repo,
        ingestion_service=ingestion_service,
    )

    evaluation_service = EvaluationService(sqlite_repo=sqlite_repo)

    return Container(
        settings=settings,
        sqlite_repo=sqlite_repo,
        minio_repo=minio_repo,
        milvus_repo=milvus_repo,
        layout_client=layout_client,
        embedding_client=embedding_client,
        llm_client=llm_client,
        parsing_service=parsing_service,
        chunking_service=chunking_service,
        embedding_service=embedding_service,
        ingestion_service=ingestion_service,
        retrieval_service=retrieval_service,
        chat_service=chat_service,
        file_service=file_service,
        evaluation_service=evaluation_service,
    )


def get_container() -> Container:
    global _container
    if _container is None:
        _container = _build_container()
    return _container


def init_runtime(container: Container) -> None:
    container.sqlite_repo.init_schema()

    try:
        container.minio_repo.ensure_bucket()
    except Exception as exc:  # noqa: BLE001
        logger.exception("MinIO bootstrap failed")
        raise RuntimeError("MinIO bootstrap failed during startup") from exc

    try:
        for collection_name in container.settings.milvus.collections:
            repo = MilvusRepo(
                host=container.settings.milvus.host,
                port=container.settings.milvus.port,
                collection_name=collection_name,
                chunk_text_max_length=container.settings.milvus.chunk_text_max_length,
            )
            repo.ensure_collection(
                dim=container.settings.embedding_api.dim,
                enable_sparse=container.settings.milvus.enable_sparse,
            )
            logger.info("Milvus collection ready on startup: %s", collection_name)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Milvus bootstrap failed")
        raise RuntimeError("Milvus bootstrap failed during startup") from exc
