from __future__ import annotations

import csv
import json
import shutil
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.db_models import AuditLog, Feedback, Task, TaskAsset, engine
from app.models.schemas import GenerateRequest
from app.services.catalog_service import CatalogService
from app.services.event_bus import EVENT_BUS
from app.services.image_generation_service import ImageGenerationService
from app.services.search_service import RetrievedItem, SearchService
from app.services.style_service import StyleService


class TaskService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.search_service = SearchService()
        self.style_service = StyleService()
        self.catalog_service = CatalogService()
        self.image_generation_service = ImageGenerationService()

    def create_and_run_task(self, payload: GenerateRequest) -> str:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC).replace(tzinfo=None)

        task = Task(
            task_id=task_id,
            session_id=payload.session_id or "anonymous",
            new_id=payload.new_id,
            status="queued",
            created_at=now,
            updated_at=now,
            image_model=self.settings.openrouter_image_model,
            llm_model=self.settings.modelscope_llm_model,
            embed_model=self.settings.openrouter_embedding_model,
        )

        with Session(engine) as session:
            session.add(task)
            session.commit()

        started = time.time()

        def emit(state: str) -> None:
            EVENT_BUS.append(task_id, state)
            self._append_audit(task_id, "task_state", {"state": state})

        try:
            emit("queued")

            # 仅检查准备数据状态，生成阶段不触发入库与哈希计算。
            self._assert_seed_data_ready(new_id=payload.new_id)

            emit("retrieving")
            refs = self.search_service.search_topk_by_new_id(payload.new_id, top_k=3)
            if len(refs) < 3:
                raise RuntimeError(f"retrieval requires top3, but got {len(refs)}")

            top3 = refs[:3]
            top3_ids = [r.product_id for r in top3]
            self._append_audit(
                task_id,
                "retrieval_top3",
                {
                    "items": [
                        {
                            "product_id": r.product_id,
                            "final_score": r.final_score,
                            "dense_score": r.dense_score,
                            "sparse_score": r.sparse_score,
                        }
                        for r in top3
                    ]
                },
            )

            new_product = self.catalog_service.get_new_product_by_id(payload.new_id)
            if not new_product:
                raise RuntimeError(f"new product not found after ingest: {payload.new_id}")

            emit("analyzing")
            style_prompt, selected_ref_id = self._analyze_style(
                task_id=task_id,
                payload=payload,
                refs=top3,
                new_product=new_product,
            )

            final_prompt = self._compose_final_prompt(
                style_prompt=style_prompt,
                prompt_hint=new_product.get("prompt_hint", ""),
                aspect_ratio=payload.aspect_ratio,
            )
            selected_ref_path = self._find_ref_image_path(top3, selected_ref_id)

            emit("generating")
            if self.settings.enable_mock:
                generated_path = self._mock_generate(task_id=task_id, source_image_path=new_product.get("image_path", ""))
            else:
                result = self.image_generation_service.generate_image(
                    task_id=task_id,
                    new_image_path=new_product.get("image_path", ""),
                    reference_image_path=selected_ref_path,
                    final_prompt=final_prompt,
                    aspect_ratio=payload.aspect_ratio,
                )
                generated_path = result.image_path
                self._append_audit(
                    task_id,
                    "image_generation",
                    {
                        "model": result.model,
                        "mime_type": result.mime_type,
                        "generated_path": generated_path,
                        "selected_ref_id": selected_ref_id,
                        "selected_ref_path": selected_ref_path,
                    },
                )

            emit("uploading")
            self._upsert_task_success(
                task_id=task_id,
                selected_ref_id=selected_ref_id,
                top3_ids=top3_ids,
                style_prompt=style_prompt,
                final_prompt=final_prompt,
                generated_key=generated_path,
                latency_ms=int((time.time() - started) * 1000),
            )

            emit("done")
        except Exception as e:
            self._upsert_task_failed(task_id=task_id, error=str(e), latency_ms=int((time.time() - started) * 1000))
            emit("failed")

        return task_id

    def _assert_seed_data_ready(self, *, new_id: str) -> None:
        products_csv = Path(self.settings.data_products_csv_path)
        new_products_csv = Path(self.settings.data_new_products_csv_path)

        if self._csv_row_count(products_csv) == 0:
            raise RuntimeError("爆款库未准备，请先点击“准备数据”（会入库并做哈希去重）")
        if self._csv_row_count(new_products_csv) == 0:
            raise RuntimeError("新品库未准备，请先点击“准备数据”")
        if self.catalog_service.get_new_product_by_id(new_id) is None:
            raise RuntimeError(f"新品ID不存在，请先准备数据或检查new_id: {new_id}")

    @staticmethod
    def _csv_row_count(path: Path) -> int:
        if not path.exists() or not path.is_file():
            return 0
        try:
            with path.open("r", encoding="utf-8", newline="") as f:
                return sum(1 for _ in csv.DictReader(f))
        except Exception:
            return 0

    def _analyze_style(
        self,
        *,
        task_id: str,
        payload: GenerateRequest,
        refs: list[RetrievedItem],
        new_product: dict,
    ) -> tuple[str, str]:
        extra_user_prompt = (payload.user_prompt_override or "").strip()

        top3_payload = [
            {
                "product_id": r.product_id,
                "category": r.category,
                "style": r.style,
                "season": r.season,
                "description": r.description,
                "final_score": r.final_score,
            }
            for r in refs[:3]
        ]

        analyze_payload = {
            "new_product": {
                "new_id": payload.new_id,
                "category": new_product.get("category", "unknown"),
                "style": new_product.get("style", "unknown"),
                "season": new_product.get("season", "unknown"),
                "prompt_hint": new_product.get("prompt_hint", ""),
            },
            "top3_references": top3_payload,
            "target_aspect_ratio": payload.aspect_ratio,
            "user_additional_constraints": extra_user_prompt,
        }

        result = self.style_service.analyze_top3(
            analyze_payload,
            new_image_path=new_product.get("image_path", ""),
            ref_image_paths=[r.image_path for r in refs[:3]],
        )

        selected_index = result.selected_index
        if selected_index not in {1, 2, 3}:
            raise RuntimeError(f"qwen selected_index must be 1/2/3, got: {selected_index}")
        selected_ref_id = refs[selected_index - 1].product_id

        style_prompt = (result.style_prompt or "").strip()
        if not style_prompt:
            raise RuntimeError("qwen style analyze missing style_prompt")
        if extra_user_prompt and extra_user_prompt not in style_prompt:
            style_prompt = f"{style_prompt}。用户补充要求: {extra_user_prompt}"

        self._append_audit(
            task_id,
            "style_analyze",
            {
                "selected_index": selected_index,
                "selected_product_id": selected_ref_id,
                "style_prompt": style_prompt[:1200],
                "raw_text": result.raw_text[:1500],
                "user_override_used_as_constraint": bool(extra_user_prompt),
            },
        )

        return style_prompt, selected_ref_id

    @staticmethod
    def _compose_final_prompt(*, style_prompt: str, prompt_hint: str, aspect_ratio: str) -> str:
        base = (
            "电商服装商业主图，突出新品主体，保持服装版型和颜色一致，"
            "构图干净、光线自然、材质细节真实，无水印无文字。"
        )
        parts = [base, f"比例 {aspect_ratio}"]
        if prompt_hint:
            parts.append(f"新品提示: {prompt_hint}")
        if style_prompt:
            parts.append(f"风格提示: {style_prompt}")
        return "。".join(parts)

    def _mock_generate(self, *, task_id: str, source_image_path: str) -> str:
        src = Path(source_image_path)
        if not src.exists() or not src.is_file():
            raise RuntimeError(f"source image not found for mock generate: {source_image_path}")

        out_dir = Path(self.settings.data_generated_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        ext = src.suffix.lower() or ".jpg"
        out_path = out_dir / f"{task_id}_mock{ext}"
        shutil.copyfile(src, out_path)
        return str(out_path.resolve())

    @staticmethod
    def _find_ref_image_path(refs: list[RetrievedItem], selected_ref_id: str | None) -> str:
        if not selected_ref_id:
            raise RuntimeError("selected_ref_id is empty")
        for r in refs:
            if r.product_id == selected_ref_id:
                return r.image_path
        raise RuntimeError(f"selected_ref_id not found in top3: {selected_ref_id}")

    def _append_audit(self, task_id: str, event_type: str, payload: dict) -> None:
        with Session(engine) as session:
            session.add(
                AuditLog(
                    task_id=task_id,
                    event_type=event_type,
                    payload=json.dumps(payload, ensure_ascii=False),
                )
            )
            session.commit()

    def _upsert_task_success(
        self,
        task_id: str,
        selected_ref_id: str | None,
        top3_ids: list[str],
        style_prompt: str,
        final_prompt: str,
        generated_key: str,
        latency_ms: int,
    ) -> None:
        with Session(engine) as session:
            task = session.get(Task, task_id)
            if not task:
                return
            task.status = "done"
            task.selected_ref_id = selected_ref_id
            task.top3_ref_ids = json.dumps(top3_ids, ensure_ascii=False)
            task.style_prompt = style_prompt
            task.final_prompt = final_prompt
            task.retry_count = 0
            task.latency_ms = latency_ms
            task.sim_warning = False
            task.sim_score = 0.0
            task.updated_at = datetime.now(UTC).replace(tzinfo=None)
            session.add(task)

            session.add(
                TaskAsset(
                    task_id=task_id,
                    asset_type="generated",
                    object_key=generated_key,
                    presigned_url=None,
                )
            )
            session.commit()

    def _upsert_task_failed(self, task_id: str, error: str, latency_ms: int) -> None:
        with Session(engine) as session:
            task = session.get(Task, task_id)
            if not task:
                return
            task.status = "failed"
            task.latency_ms = latency_ms
            task.updated_at = datetime.now(UTC).replace(tzinfo=None)
            session.add(task)
            session.commit()

        self._append_audit(task_id, "task_error", {"error": error})

    def list_tasks(self) -> list[Task]:
        with Session(engine) as session:
            rows = session.exec(select(Task).order_by(Task.created_at.desc())).all()
            return list(rows)

    def get_task(self, task_id: str) -> Task | None:
        with Session(engine) as session:
            return session.get(Task, task_id)

    def get_generated_asset_path(self, task_id: str) -> str | None:
        with Session(engine) as session:
            stmt = (
                select(TaskAsset)
                .where(TaskAsset.task_id == task_id, TaskAsset.asset_type == "generated")
                .order_by(TaskAsset.created_at.desc())
            )
            row = session.exec(stmt).first()
            if not row:
                return None
            return row.object_key

    def upsert_feedback(self, task_id: str, feedback_type: str, feedback_text: str | None) -> None:
        with Session(engine) as session:
            row = session.exec(select(Feedback).where(Feedback.task_id == task_id)).first()
            if row:
                row.feedback_type = feedback_type
                row.feedback_text = feedback_text
                row.created_at = datetime.now(UTC).replace(tzinfo=None)
                session.add(row)
            else:
                session.add(
                    Feedback(
                        task_id=task_id,
                        feedback_type=feedback_type,
                        feedback_text=feedback_text,
                    )
                )
            session.commit()

    def metrics_summary(self, days: int = 30) -> tuple[int, float, float]:
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
        with Session(engine) as session:
            tasks = list(session.exec(select(Task).where(Task.created_at >= cutoff)).all())
            total = len(tasks)
            if total == 0:
                return 0, 0.0, 0.0

            task_ids = [t.task_id for t in tasks]
            feedback_rows = list(session.exec(select(Feedback).where(Feedback.task_id.in_(task_ids))).all())
            feedback_map = {f.task_id: f.feedback_type for f in feedback_rows}

            likes = sum(1 for tid in task_ids if feedback_map.get(tid) == "up")
            dislikes = sum(1 for tid in task_ids if feedback_map.get(tid) == "down")

            success_rate = likes / total
            dislike_rate = dislikes / total
            return total, success_rate, dislike_rate

    def get_events(self, task_id: str) -> list[str]:
        events = EVENT_BUS.get(task_id)
        if events:
            return events

        # Fallback for restarted process: derive at least one state from persisted status.
        task = self.get_task(task_id)
        if not task:
            return []
        if task.status == "done":
            return ["queued", "retrieving", "analyzing", "generating", "uploading", "done"]
        if task.status == "failed":
            return ["queued", "failed"]
        return [task.status]
