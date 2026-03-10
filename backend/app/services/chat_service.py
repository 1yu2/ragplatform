from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.clients.llm_client import LlmClient
from app.utils.stream_util import sse_event
from app.utils.text_util import is_ambiguous_question
from app.utils.timer_util import Stopwatch


class ChatService:
    def __init__(
        self,
        llm_client: LlmClient,
        retrieval_service,
        sqlite_repo,
        refuse_threshold: float,
        long_question_threshold: int,
    ):
        self.llm_client = llm_client
        self.retrieval_service = retrieval_service
        self.sqlite_repo = sqlite_repo
        self.refuse_threshold = refuse_threshold
        self.long_question_threshold = long_question_threshold

    async def _rewrite_question(self, question: str) -> str:
        prompt = [
            {"role": "system", "content": "你是问题改写助手。保持语义不变，只输出改写后的单句问题。"},
            {"role": "user", "content": question},
        ]
        rewritten = await self.llm_client.complete(prompt)
        return rewritten or question

    def _need_rewrite(self, question: str) -> bool:
        return len(question) >= self.long_question_threshold or is_ambiguous_question(question)

    def _parse_stream_line(self, line: str) -> str:
        payload = line.removeprefix("data:").strip()
        if not payload:
            return ""
        try:
            data = json.loads(payload)
            choices = data.get("choices", [])
            if not choices:
                return ""
            delta = choices[0].get("delta", {})
            return str(delta.get("content", ""))
        except json.JSONDecodeError:
            return ""

    def _citations(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cites = []
        for doc in docs[:5]:
            file_name = doc.get("file_name") or "unknown"
            page = doc.get("page", 0)
            paragraph_id = doc.get("paragraph_id") or "p0"
            chunk_text = str(doc.get("chunk_text", "") or "")
            cites.append(
                {
                    "ref": f"[{file_name}-{page}-{paragraph_id}]",
                    "snippet": chunk_text[:200],
                    "markdown": chunk_text,
                    "score": float(doc.get("fused_score", 0.0)),
                }
            )
        return cites

    async def build_citations_for_query(self, query: str) -> list[dict[str, Any]]:
        if not str(query or "").strip():
            return []
        docs = await self.retrieval_service.retrieve(query)
        return self._citations(docs)

    async def stream_answer(self, question: str):
        watch = Stopwatch()
        rewritten = question
        if self._need_rewrite(question):
            try:
                rewritten = await self._rewrite_question(question)
            except Exception:  # noqa: BLE001
                rewritten = question

        docs = await self.retrieval_service.retrieve(rewritten)
        top1_dense = float(docs[0].get("dense_score", 0.0)) if docs else 0.0
        citations = self._citations(docs)

        if not docs or top1_dense < self.refuse_threshold:
            answer = "无法回答"
            self.sqlite_repo.insert_chat_log(
                {
                    "id": str(uuid.uuid4()),
                    "question": question,
                    "rewritten_question": rewritten,
                    "answer": answer,
                    "is_refused": 1,
                    "top1_score": top1_dense,
                    "latency_first_token_ms": watch.elapsed_ms(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "citations": citations,
                }
            )
            yield sse_event({"type": "final", "data": {"answer": answer, "is_refused": True, "top1_score": top1_dense, "citations": citations}})
            return

        context = "\n\n".join(
            [
                f"参考[{idx+1}] {c['ref']}\n{d.get('chunk_text', '')}"
                for idx, (d, c) in enumerate(zip(docs, citations))
            ]
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "你是中文问答助手。只能基于提供的参考内容回答，不确定时明确说无法回答。"
                    "输出使用 Markdown。"
                    "引用时在对应句末使用角标样式 [1] [2]，数字必须与参考资料编号一致。"
                ),
            },
            {"role": "user", "content": f"问题:\n{rewritten}\n\n参考资料:\n{context}"},
        ]

        answer_parts: list[str] = []
        first_token_ms: int | None = None
        try:
            async for line in self.llm_client.stream_chat(messages):
                token = self._parse_stream_line(line)
                if not token:
                    continue
                answer_parts.append(token)
                if first_token_ms is None:
                    first_token_ms = watch.elapsed_ms()
                yield sse_event({"type": "token", "data": token})
        except Exception as exc:  # noqa: BLE001
            # 流式上游失败时不抛给 ASGI，返回可读结果给前端。
            partial = "".join(answer_parts).strip()
            fallback_answer = partial or "无法回答"
            self.sqlite_repo.insert_chat_log(
                {
                    "id": str(uuid.uuid4()),
                    "question": question,
                    "rewritten_question": rewritten,
                    "answer": fallback_answer,
                    "is_refused": 1 if not partial else 0,
                    "top1_score": top1_dense,
                    "latency_first_token_ms": first_token_ms or watch.elapsed_ms(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "citations": citations,
                }
            )
            yield sse_event(
                {
                    "type": "final",
                    "data": {
                        "answer": fallback_answer,
                        "is_refused": not bool(partial),
                        "top1_score": top1_dense,
                        "citations": citations,
                        "error": str(exc),
                    },
                }
            )
            return

        answer = "".join(answer_parts).strip() or "无法回答"
        self.sqlite_repo.insert_chat_log(
            {
                "id": str(uuid.uuid4()),
                "question": question,
                "rewritten_question": rewritten,
                "answer": answer,
                "is_refused": 0,
                "top1_score": top1_dense,
                "latency_first_token_ms": first_token_ms or watch.elapsed_ms(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "citations": citations,
            }
        )
        yield sse_event(
            {
                "type": "final",
                "data": {
                    "answer": answer,
                    "is_refused": False,
                    "top1_score": top1_dense,
                    "citations": citations,
                },
            }
        )
