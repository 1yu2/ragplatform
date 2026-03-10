from __future__ import annotations

import asyncio
import logging
import uuid
from io import BytesIO
from datetime import datetime, timezone

from pypdf import PdfReader

from app.core.constants import TaskStatus
from app.repositories.milvus_repo import MilvusRepo
from app.repositories.sqlite_repo import SqliteRepo
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.parsing_service import ParsingService
from app.utils.pdf_util import split_pdf_bytes, split_pdf_bytes_range

logger = logging.getLogger(__name__)

NOISE_TEXTS = {
    "number",
    "footnote",
    "header",
    "header_image",
    "footer",
    "footer_image",
    "aside_text",
}
NOISE_BLOCK_TYPES = {"ignore", *NOISE_TEXTS}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IngestionService:
    def __init__(
        self,
        sqlite_repo: SqliteRepo,
        parsing_service: ParsingService,
        chunking_service: ChunkingService,
        embedding_service: EmbeddingService,
        milvus_repo: MilvusRepo,
        minio_repo,
        layout_client,
        embedding_dim: int = 1024,
        enable_sparse: bool = True,
        use_presigned_url: bool = True,
        presigned_expire_seconds: int = 1200,
        enforce_page_coverage: bool = True,
        min_total_pages_to_enforce: int = 5,
        min_parsed_pages: int = 2,
        min_page_coverage_ratio: float = 0.2,
        enable_slice_fallback: bool = True,
        slice_pages: int = 3,
        parse_batch_pages: int = 512,
        min_parse_batch_pages: int = 1,
        skip_failed_pages: bool = True,
        max_concurrent_tasks: int = 1,
    ):
        self.sqlite_repo = sqlite_repo
        self.parsing_service = parsing_service
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.milvus_repo = milvus_repo
        self.minio_repo = minio_repo
        self.layout_client = layout_client
        self.embedding_dim = embedding_dim
        self.enable_sparse = enable_sparse
        self.use_presigned_url = use_presigned_url
        self.presigned_expire_seconds = presigned_expire_seconds
        self.enforce_page_coverage = enforce_page_coverage
        self.min_total_pages_to_enforce = min_total_pages_to_enforce
        self.min_parsed_pages = min_parsed_pages
        self.min_page_coverage_ratio = min_page_coverage_ratio
        self.enable_slice_fallback = enable_slice_fallback
        self.slice_pages = max(1, slice_pages)
        self.parse_batch_pages = max(1, parse_batch_pages)
        self.min_parse_batch_pages = max(1, min_parse_batch_pages)
        self.skip_failed_pages = bool(skip_failed_pages)
        self.max_concurrent_tasks = max(1, int(max_concurrent_tasks))
        self._task_semaphore = asyncio.Semaphore(self.max_concurrent_tasks)

    @staticmethod
    def _count_pdf_pages(content: bytes) -> int:
        # 使用 pypdf 获取真实页数，失败时最少返回 1。
        try:
            reader = PdfReader(BytesIO(content))
            return max(len(reader.pages), 1)
        except Exception:  # noqa: BLE001
            return 1

    @staticmethod
    def _extract_total_pages_from_layout(raw: dict) -> int | None:
        if not isinstance(raw, dict):
            return None
        candidates = []
        if isinstance(raw.get("dataInfo"), dict):
            candidates.append(raw["dataInfo"])
        result = raw.get("result")
        if isinstance(result, dict):
            if isinstance(result.get("dataInfo"), dict):
                candidates.append(result["dataInfo"])
            if isinstance(result.get("meta"), dict):
                candidates.append(result["meta"])
        for info in candidates:
            num_pages = info.get("numPages") or info.get("num_pages") or info.get("pageCount")
            if isinstance(num_pages, int) and num_pages > 0:
                return num_pages
            if isinstance(num_pages, str) and num_pages.isdigit() and int(num_pages) > 0:
                return int(num_pages)
            pages = info.get("pages")
            if isinstance(pages, list) and pages:
                return len(pages)
        return None

    @staticmethod
    def _summarize_result_shape(raw: dict) -> str:
        if not isinstance(raw, dict):
            return f"raw_type={type(raw).__name__}"
        result = raw.get("result")
        if isinstance(result, list):
            first_keys = list(result[0].keys())[:12] if result and isinstance(result[0], dict) else []
            return f"result_type=list result_len={len(result)} first_item_keys={first_keys}"
        if isinstance(result, dict):
            parts = []
            for k, v in list(result.items())[:12]:
                if isinstance(v, list):
                    parts.append(f"{k}:list[{len(v)}]")
                elif isinstance(v, dict):
                    parts.append(f"{k}:dict[{len(v)}]")
                else:
                    parts.append(f"{k}:{type(v).__name__}")
            return "result_type=dict " + ", ".join(parts)
        return f"result_type={type(result).__name__}"

    @staticmethod
    def _shift_pages(blocks: list[dict], offset: int) -> list[dict]:
        if offset <= 0:
            return blocks
        out: list[dict] = []
        for b in blocks:
            nb = dict(b)
            nb["page"] = int(nb.get("page", 1)) + offset
            out.append(nb)
        return out

    async def _parse_upload_part_adaptive(
        self,
        file_name: str,
        part_bytes: bytes,
        part_start_page: int,
        chunk_pages: int,
    ) -> list[dict]:
        try:
            temp_key = f"__tmp/layout_parts/{uuid.uuid4().hex}_p{part_start_page}.pdf"
            self.minio_repo.upload_bytes(temp_key, part_bytes)
            try:
                if self.use_presigned_url:
                    part_url = self.minio_repo.presigned_get_url(
                        temp_key,
                        expires_seconds=self.presigned_expire_seconds,
                    )
                    part_mode = "tmp_presigned"
                else:
                    part_url = self.minio_repo.object_url(temp_key)
                    part_mode = "tmp_object"
                logger.info(
                    "layout part parse request mode=%s start_page=%s chunk_pages=%s file=%s",
                    part_mode,
                    part_start_page,
                    chunk_pages,
                    part_url,
                )
                part_raw = await self.layout_client.parse(part_url)
            finally:
                try:
                    self.minio_repo.remove_object(temp_key)
                except Exception:  # noqa: BLE001
                    pass
            part_blocks = self.parsing_service.normalize_layout_result(part_raw)
            part_blocks = self.parsing_service.filter_header_footer(part_blocks)
            return self._shift_pages(part_blocks, part_start_page - 1)
        except Exception as exc:  # noqa: BLE001
            if chunk_pages <= self.min_parse_batch_pages:
                if self.skip_failed_pages and chunk_pages == 1:
                    logger.error(
                        "layout skip failed single page start_page=%s err=%s",
                        part_start_page,
                        exc,
                    )
                    return [
                        {
                            "id": str(uuid.uuid4()),
                            "page": int(part_start_page),
                            "block_type": "ignore",
                            "layout_label": "layout_parse_failed",
                            "order": 0,
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 0.0,
                            "y2": 0.0,
                            "text": f"[PAGE_PARSE_FAILED] page={part_start_page}",
                            "source": "layout_failed_page",
                            "raw": {"error": str(exc)},
                        }
                    ]
                raise RuntimeError(
                    f"layout adaptive parse failed at min chunk_pages={chunk_pages}, start_page={part_start_page}: {exc}"
                ) from exc

            next_chunk_pages = max(self.min_parse_batch_pages, chunk_pages // 2)
            logger.warning(
                "layout adaptive split start_page=%s chunk_pages=%s -> %s err=%s",
                part_start_page,
                chunk_pages,
                next_chunk_pages,
                exc,
            )
            sub_chunks, _ = split_pdf_bytes(part_bytes, next_chunk_pages)
            merged: list[dict] = []
            for rel_start, sub_bytes in sub_chunks:
                absolute_start = part_start_page + rel_start - 1
                sub_blocks = await self._parse_upload_part_adaptive(
                    file_name=file_name,
                    part_bytes=sub_bytes,
                    part_start_page=absolute_start,
                    chunk_pages=next_chunk_pages,
                )
                merged.extend(sub_blocks)
            return merged

    async def _slice_parse_blocks(self, file_name: str, pdf_bytes: bytes, chunk_pages: int) -> tuple[list[dict], int]:
        chunks, total_pages = split_pdf_bytes(pdf_bytes, chunk_pages)
        merged_blocks: list[dict] = []
        total_chunks = len(chunks)
        for idx, (start_page, part_bytes) in enumerate(chunks, start=1):
            logger.info(
                "layout sliced parse part=%s/%s start_page=%s chunk_pages=%s",
                idx,
                total_chunks,
                start_page,
                chunk_pages,
            )
            part_blocks = await self._parse_upload_part_adaptive(
                file_name=file_name,
                part_bytes=part_bytes,
                part_start_page=start_page,
                chunk_pages=chunk_pages,
            )
            merged_blocks.extend(part_blocks)
        return merged_blocks, total_pages

    async def _slice_parse_blocks_range(
        self,
        file_name: str,
        pdf_bytes: bytes,
        chunk_pages: int,
        start_page: int,
        end_page: int | None = None,
    ) -> tuple[list[dict], int]:
        chunks, total_pages = split_pdf_bytes_range(
            pdf_bytes=pdf_bytes,
            chunk_pages=chunk_pages,
            start_page=start_page,
            end_page=end_page,
        )
        merged_blocks: list[dict] = []
        total_chunks = len(chunks)
        for idx, (part_start_page, part_bytes) in enumerate(chunks, start=1):
            logger.info(
                "layout ranged parse part=%s/%s start_page=%s chunk_pages=%s range=[%s,%s]",
                idx,
                total_chunks,
                part_start_page,
                chunk_pages,
                start_page,
                end_page or total_pages,
            )
            part_blocks = await self._parse_upload_part_adaptive(
                file_name=file_name,
                part_bytes=part_bytes,
                part_start_page=part_start_page,
                chunk_pages=chunk_pages,
            )
            merged_blocks.extend(part_blocks)
        return merged_blocks, total_pages

    async def _run_task_with_retries(self, task_id: str, file_id: str) -> None:
        self.sqlite_repo.update_task(task_id, status=TaskStatus.RUNNING.value, started_at=_now())
        self.sqlite_repo.update_file_status(file_id, TaskStatus.RUNNING.value)
        retries = 3
        for attempt in range(1, retries + 1):
            try:
                file_record = self.sqlite_repo.get_file(file_id)
                if not file_record:
                    raise RuntimeError(f"file not found for task: {task_id}")
                obj_key = file_record["minio_object_key"]
                pdf_bytes_for_slice = self.minio_repo.get_object_bytes(obj_key)
                pdf_total_est = self._count_pdf_pages(pdf_bytes_for_slice)
                parse_batch_pages = max(1, self.parse_batch_pages)
                layout_total_pages = None
                raw: dict | None = None

                if self.use_presigned_url:
                    file_url = self.minio_repo.presigned_get_url(
                        obj_key,
                        expires_seconds=self.presigned_expire_seconds,
                    )
                    url_mode = "presigned"
                else:
                    file_url = self.minio_repo.object_url(obj_key)
                    url_mode = "object"

                blocks: list[dict] = []
                try:
                    logger.info("layout parse request task=%s mode=%s file=%s", task_id, url_mode, file_url)
                    raw = await self.layout_client.parse(file_url)
                    if isinstance(raw, dict):
                        logger.info("layout parse raw task=%s top_keys=%s", task_id, list(raw.keys())[:20])
                        logger.info("layout parse raw-shape task=%s %s", task_id, self._summarize_result_shape(raw))
                    blocks = self.parsing_service.normalize_layout_result(raw)
                    blocks = self.parsing_service.filter_header_footer(blocks)
                    layout_total_pages = self._extract_total_pages_from_layout(raw)
                except Exception as url_exc:  # noqa: BLE001
                    logger.warning("layout url parse failed task=%s err=%s; fallback to full batch ranged parse", task_id, url_exc)
                    blocks, batch_total = await self._slice_parse_blocks(
                        file_name=file_record["file_name"],
                        pdf_bytes=pdf_bytes_for_slice,
                        chunk_pages=parse_batch_pages,
                    )
                    layout_total_pages = batch_total

                # 对超出 512 页的文档，优先保留 URL 解析结果，再补解析尾页，减少整体分片导致的不稳定。
                if raw is not None and pdf_total_est > parse_batch_pages:
                    page_set_head = {int(b.get("page", 1)) for b in blocks}
                    tail_start = parse_batch_pages + 1
                    if tail_start <= pdf_total_est:
                        logger.info(
                            "layout tail ranged parse task=%s total_pages=%s head_pages=%s tail_start=%s",
                            task_id,
                            pdf_total_est,
                            len(page_set_head),
                            tail_start,
                        )
                        tail_blocks, _ = await self._slice_parse_blocks_range(
                            file_name=file_record["file_name"],
                            pdf_bytes=pdf_bytes_for_slice,
                            chunk_pages=parse_batch_pages,
                            start_page=tail_start,
                            end_page=pdf_total_est,
                        )
                        # 防止重复页块冲突：保留头部 URL 结果 + 尾部新增页
                        if tail_blocks:
                            head_pages = {int(b.get("page", 1)) for b in blocks}
                            blocks.extend([b for b in tail_blocks if int(b.get("page", 1)) not in head_pages])
                            layout_total_pages = pdf_total_est

                logger.info("layout parse normalized task=%s blocks=%s", task_id, len(blocks))
                if not blocks:
                    raise RuntimeError("layout parse returned empty blocks")
                failed_pages = sorted({int(b.get("page", 1)) for b in blocks if str(b.get("source", "")) == "layout_failed_page"})
                if failed_pages:
                    logger.warning(
                        "layout parse has failed pages task=%s count=%s sample=%s",
                        task_id,
                        len(failed_pages),
                        failed_pages[:20],
                    )
                page_set = sorted({int(b.get("page", 1)) for b in blocks})
                parsed_pages = len(page_set)

                if (
                    self.enable_slice_fallback
                    and raw is not None
                    and layout_total_pages is not None
                    and layout_total_pages <= self.slice_pages
                    and pdf_total_est > layout_total_pages
                ):
                    try:
                        logger.info(
                            "layout slice fallback task=%s trigger=true layout_pages=%s pdf_total_est=%s slice_pages=%s",
                            task_id,
                            layout_total_pages,
                            pdf_total_est,
                            self.slice_pages,
                        )
                        sliced_blocks, sliced_total = await self._slice_parse_blocks(
                            file_name=file_record["file_name"],
                            pdf_bytes=pdf_bytes_for_slice,
                            chunk_pages=self.slice_pages,
                        )
                        if sliced_blocks:
                            blocks = sliced_blocks
                            page_set = sorted({int(b.get("page", 1)) for b in blocks})
                            parsed_pages = len(page_set)
                            layout_total_pages = sliced_total
                            logger.info(
                                "layout slice fallback task=%s merged_blocks=%s merged_pages=%s",
                                task_id,
                                len(blocks),
                                parsed_pages,
                            )
                    except Exception as slice_exc:  # noqa: BLE001
                        logger.warning("layout slice fallback failed task=%s err=%s", task_id, slice_exc)

                if self.enforce_page_coverage:
                    total_pages = layout_total_pages
                    if total_pages is None:
                        total_pages = pdf_total_est
                    coverage = parsed_pages / max(total_pages, 1)
                    logger.info(
                        "layout parse coverage task=%s parsed_pages=%s total_pages_est=%s coverage=%.4f pages_sample=%s",
                        task_id,
                        parsed_pages,
                        total_pages,
                        coverage,
                        page_set[:20],
                    )
                    if (
                        total_pages >= self.min_total_pages_to_enforce
                        and (parsed_pages < self.min_parsed_pages or coverage < self.min_page_coverage_ratio)
                    ):
                        raise RuntimeError(
                            f"layout parse coverage too low: parsed_pages={parsed_pages}, total_pages_est={total_pages}, coverage={coverage:.4f}"
                        )
                self.sqlite_repo.replace_blocks(file_id, blocks)
                logger.info("ingestion task=%s step=replace_blocks blocks=%s", task_id, len(blocks))

                chunks = self.chunking_service.build_chunks(file_id, blocks)
                if not chunks:
                    raise RuntimeError("chunking produced empty chunks")
                chunks = [
                    c
                    for c in chunks
                    if str(c.get("block_type", "")).lower() not in NOISE_BLOCK_TYPES
                    and str(c.get("chunk_text", "")).strip()
                    and str(c.get("chunk_text", "")).strip().lower() not in NOISE_TEXTS
                ]
                if not chunks:
                    raise RuntimeError("all chunks filtered as noise")
                self.sqlite_repo.replace_chunks(file_id, chunks)
                logger.info("ingestion task=%s step=replace_chunks chunks=%s", task_id, len(chunks))

                texts = [c["chunk_text"] for c in chunks]
                embeddings = await self.embedding_service.embed_texts(texts)
                logger.info("ingestion task=%s step=embedding vectors=%s", task_id, len(embeddings))

                milvus_items = []
                for idx, chunk in enumerate(chunks):
                    emb = embeddings[idx] if idx < len(embeddings) else {}
                    dense = emb.get("embedding") or [0.0] * 1024
                    sparse = emb.get("spare_embedding") or emb.get("sparse_embedding") or {}
                    milvus_items.append(
                        {
                            "chunk_id": chunk["id"],
                            "file_id": file_id,
                            "file_name": file_record["file_name"],
                            "page": chunk["page"],
                            "paragraph_id": chunk["paragraph_id"],
                            "block_type": chunk["block_type"],
                            "chunk_text": chunk["chunk_text"],
                            "dense_vector": dense,
                            "sparse_vector": sparse,
                        }
                    )

                self.milvus_repo.ensure_collection(dim=self.embedding_dim, enable_sparse=self.enable_sparse)
                # 全量重建时先删掉该文件旧向量，避免脏数据残留。
                self.milvus_repo.delete_by_file_id(file_id)
                self.milvus_repo.upsert_chunks(milvus_items)
                logger.info("ingestion task=%s step=milvus_upsert items=%s", task_id, len(milvus_items))

                self.sqlite_repo.update_task(task_id, status=TaskStatus.SUCCESS.value, retry_count=attempt - 1, finished_at=_now())
                self.sqlite_repo.update_file_status(file_id, TaskStatus.SUCCESS.value)
                return
            except Exception as exc:  # noqa: BLE001
                logger.exception("ingestion failed task=%s attempt=%s", task_id, attempt)
                if attempt >= retries:
                    self.sqlite_repo.update_task(
                        task_id,
                        status=TaskStatus.FAILED.value,
                        retry_count=attempt,
                        error_message=str(exc),
                        finished_at=_now(),
                    )
                    self.sqlite_repo.update_file_status(file_id, TaskStatus.FAILED.value)
                    return
                self.sqlite_repo.update_task(
                    task_id,
                    status=TaskStatus.RUNNING.value,
                    retry_count=attempt,
                    error_message=str(exc),
                )
                await asyncio.sleep(1)

    async def run_task(self, task_id: str) -> None:
        task = self.sqlite_repo.get_task(task_id)
        if not task:
            return
        file_id = task["file_id"]
        logger.info(
            "ingestion queue wait task=%s file_id=%s max_concurrent_tasks=%s",
            task_id,
            file_id,
            self.max_concurrent_tasks,
        )
        async with self._task_semaphore:
            logger.info("ingestion queue acquired task=%s file_id=%s", task_id, file_id)
            await self._run_task_with_retries(task_id, file_id)
