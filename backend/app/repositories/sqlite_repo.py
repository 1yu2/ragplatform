from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.utils.layout_flow import build_logical_units, build_markdown_pages, sort_blocks


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
        col_names = {str(c["name"]) for c in cols}
        if column not in col_names:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")

    def init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    sha256 TEXT NOT NULL UNIQUE,
                    size_bytes INTEGER NOT NULL,
                    minio_object_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ingest_tasks (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS file_blocks (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    page INTEGER,
                    block_type TEXT,
                    x1 REAL,
                    y1 REAL,
                    x2 REAL,
                    y2 REAL,
                    text TEXT,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    page INTEGER,
                    paragraph_id TEXT,
                    block_type TEXT,
                    chunk_index INTEGER,
                    chunk_text TEXT,
                    source_offset INTEGER,
                    metadata_json TEXT
                );

                CREATE TABLE IF NOT EXISTS chat_logs (
                    id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    rewritten_question TEXT,
                    answer TEXT,
                    is_refused INTEGER NOT NULL,
                    top1_score REAL NOT NULL,
                    latency_first_token_ms INTEGER,
                    created_at TEXT NOT NULL,
                    citations_json TEXT
                );

                CREATE TABLE IF NOT EXISTS evaluations (
                    id TEXT PRIMARY KEY,
                    dataset_size INTEGER NOT NULL,
                    faithfulness REAL NOT NULL,
                    answer_relevancy REAL NOT NULL,
                    context_precision REAL NOT NULL,
                    context_recall REAL NOT NULL,
                    overall_score REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._ensure_column(conn, "chat_logs", "citations_json", "citations_json TEXT")

    def create_file(self, payload: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO files (id, file_name, sha256, size_bytes, minio_object_key, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["file_name"],
                    payload["sha256"],
                    payload["size_bytes"],
                    payload["minio_object_key"],
                    payload["status"],
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )

    def update_file_status(self, file_id: str, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE files SET status = ?, updated_at = ? WHERE id = ?",
                (status, now_iso(), file_id),
            )

    def get_file_by_sha256(self, sha256: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM files WHERE sha256 = ?", (sha256,)).fetchone()
            return dict(row) if row else None

    def get_file(self, file_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
            return dict(row) if row else None

    def list_files(self, limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
        with self._conn() as conn:
            if limit is None:
                rows = conn.execute("SELECT * FROM files ORDER BY created_at DESC").fetchall()
                return [dict(r) for r in rows]
            rows = conn.execute(
                "SELECT * FROM files ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (max(1, int(limit)), max(0, int(offset))),
            ).fetchall()
            return [dict(r) for r in rows]

    def count_files(self) -> int:
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(1) AS c FROM files").fetchone()
            return int(row["c"]) if row else 0

    def delete_file_cascade(self, file_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))
            conn.execute("DELETE FROM file_blocks WHERE file_id = ?", (file_id,))
            conn.execute("DELETE FROM ingest_tasks WHERE file_id = ?", (file_id,))
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))

    def create_task(self, payload: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO ingest_tasks (id, file_id, status, retry_count, error_message, started_at, finished_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["file_id"],
                    payload["status"],
                    payload["retry_count"],
                    payload.get("error_message"),
                    payload.get("started_at"),
                    payload.get("finished_at"),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM ingest_tasks WHERE id = ?", (task_id,)).fetchone()
            return dict(row) if row else None

    def get_task_by_file_id(self, file_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM ingest_tasks WHERE file_id = ? ORDER BY created_at DESC LIMIT 1",
                (file_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_task(
        self,
        task_id: str,
        *,
        status: str,
        retry_count: int | None = None,
        error_message: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        sets = ["status = ?", "updated_at = ?"]
        args: list[Any] = [status, now_iso()]

        if retry_count is not None:
            sets.append("retry_count = ?")
            args.append(retry_count)
        if error_message is not None:
            sets.append("error_message = ?")
            args.append(error_message)
        if started_at is not None:
            sets.append("started_at = ?")
            args.append(started_at)
        if finished_at is not None:
            sets.append("finished_at = ?")
            args.append(finished_at)

        args.append(task_id)
        with self._conn() as conn:
            conn.execute(f"UPDATE ingest_tasks SET {', '.join(sets)} WHERE id = ?", args)

    def replace_blocks(self, file_id: str, blocks: list[dict[str, Any]]) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM file_blocks WHERE file_id = ?", (file_id,))
            for block in blocks:
                conn.execute(
                    """
                    INSERT INTO file_blocks (id, file_id, page, block_type, x1, y1, x2, y2, text, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        block["id"],
                        file_id,
                        block.get("page"),
                        block.get("block_type"),
                        block.get("x1"),
                        block.get("y1"),
                        block.get("x2"),
                        block.get("y2"),
                        block.get("text", ""),
                        json.dumps(block, ensure_ascii=False),
                    ),
                )

    def replace_chunks(self, file_id: str, chunks: list[dict[str, Any]]) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))
            for chunk in chunks:
                conn.execute(
                    """
                    INSERT INTO chunks (id, file_id, page, paragraph_id, block_type, chunk_index, chunk_text, source_offset, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk["id"],
                        file_id,
                        chunk.get("page", 0),
                        chunk.get("paragraph_id", ""),
                        chunk.get("block_type", "text"),
                        chunk.get("chunk_index", 0),
                        chunk.get("chunk_text", ""),
                        chunk.get("source_offset", 0),
                        json.dumps(chunk.get("metadata", {}), ensure_ascii=False),
                    ),
                )

    def get_preview(self, file_id: str) -> dict[str, Any]:
        with self._conn() as conn:
            raw_blocks = [
                dict(r)
                for r in conn.execute(
                    "SELECT id, page, block_type, x1, y1, x2, y2, text, raw_json FROM file_blocks WHERE file_id = ? ORDER BY page, id",
                    (file_id,),
                ).fetchall()
            ]
            full_blocks: list[dict[str, Any]] = []
            blocks_for_table: list[dict[str, Any]] = []
            for row in raw_blocks:
                raw_json = row.pop("raw_json", None)
                raw_obj: dict[str, Any] = {}
                if raw_json:
                    try:
                        raw_obj = json.loads(raw_json)
                    except Exception:  # noqa: BLE001
                        raw_obj = {}

                full = dict(raw_obj) if isinstance(raw_obj, dict) else {}
                full["id"] = row.get("id")
                full["page"] = row.get("page")
                full["block_type"] = row.get("block_type")
                full["x1"] = row.get("x1")
                full["y1"] = row.get("y1")
                full["x2"] = row.get("x2")
                full["y2"] = row.get("y2")
                full["text"] = row.get("text")
                full["layout_label"] = str(full.get("layout_label", "") or "")
                full["source"] = str(full.get("source", "") or "")
                full["order"] = int(full.get("order") or 0)
                full_blocks.append(full)

                blocks_for_table.append(
                    {
                        "id": full["id"],
                        "page": full["page"],
                        "block_type": full["block_type"],
                        "layout_label": full["layout_label"],
                        "source": full["source"],
                        "x1": full["x1"],
                        "y1": full["y1"],
                        "x2": full["x2"],
                        "y2": full["y2"],
                        "order": full["order"],
                        "text": full["text"],
                    }
                )

            chunks = [
                dict(r)
                for r in conn.execute(
                    "SELECT id, page, paragraph_id, block_type, chunk_index, chunk_text, source_offset FROM chunks WHERE file_id = ? ORDER BY page, paragraph_id, chunk_index",
                    (file_id,),
                ).fetchall()
            ]
            sorted_blocks = sort_blocks(blocks_for_table)
            units = build_logical_units(full_blocks)
            markdown_pages = build_markdown_pages(units)
            for i, b in enumerate(sorted_blocks, start=1):
                b["seq"] = i
            for i, u in enumerate(units, start=1):
                u["seq"] = i
            return {"blocks": sorted_blocks, "chunks": chunks, "markdown_pages": markdown_pages, "units": units}

    def list_chunks(self, limit: int = 1000) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, file_id, page, paragraph_id, block_type, chunk_index, chunk_text FROM chunks ORDER BY rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, file_id, page, paragraph_id, block_type, chunk_index, chunk_text, source_offset, metadata_json FROM chunks WHERE id = ?",
                (chunk_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_chunk_text(self, chunk_id: str, chunk_text: str, metadata: dict[str, Any] | None = None) -> None:
        with self._conn() as conn:
            if metadata is None:
                conn.execute(
                    "UPDATE chunks SET chunk_text = ? WHERE id = ?",
                    (chunk_text, chunk_id),
                )
            else:
                conn.execute(
                    "UPDATE chunks SET chunk_text = ?, metadata_json = ? WHERE id = ?",
                    (chunk_text, json.dumps(metadata, ensure_ascii=False), chunk_id),
                )

    def delete_chunk(self, chunk_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM chunks WHERE id = ?", (chunk_id,))

    def insert_chat_log(self, payload: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO chat_logs (id, question, rewritten_question, answer, is_refused, top1_score, latency_first_token_ms, created_at, citations_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["question"],
                    payload.get("rewritten_question"),
                    payload.get("answer"),
                    payload["is_refused"],
                    payload["top1_score"],
                    payload.get("latency_first_token_ms"),
                    payload["created_at"],
                    json.dumps(payload.get("citations", []), ensure_ascii=False),
                ),
            )

    def list_chat_logs(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, question, rewritten_question, answer, is_refused, top1_score, latency_first_token_ms, created_at, citations_json
                FROM chat_logs
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_chat_log(self, chat_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT id, question, rewritten_question, answer, is_refused, top1_score, latency_first_token_ms, created_at, citations_json
                FROM chat_logs
                WHERE id = ?
                """,
                (chat_id,),
            ).fetchone()
            return dict(row) if row else None

    def delete_chat_log(self, chat_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM chat_logs WHERE id = ?", (chat_id,))

    def clear_chat_logs(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM chat_logs")

    def update_chat_citations(self, chat_id: str, citations: list[dict[str, Any]]) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE chat_logs SET citations_json = ? WHERE id = ?",
                (json.dumps(citations, ensure_ascii=False), chat_id),
            )

    def insert_evaluation(self, payload: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO evaluations (id, dataset_size, faithfulness, answer_relevancy, context_precision, context_recall, overall_score, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["dataset_size"],
                    payload["faithfulness"],
                    payload["answer_relevancy"],
                    payload["context_precision"],
                    payload["context_recall"],
                    payload["overall_score"],
                    payload["status"],
                    payload["created_at"],
                ),
            )

    def latest_evaluation(self) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM evaluations ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def list_evaluations(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM evaluations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
