from __future__ import annotations

import math
import re
from typing import Any

from app.services.embedding_service import EmbeddingService


class RetrievalService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        milvus_repo,
        sqlite_repo,
        top_k: int,
        dense_weight: float,
        bm25_weight: float,
    ):
        self.embedding_service = embedding_service
        self.milvus_repo = milvus_repo
        self.sqlite_repo = sqlite_repo
        self.top_k = top_k
        self.dense_weight = dense_weight
        self.bm25_weight = bm25_weight

    def _tokens(self, text: str) -> list[str]:
        text = text.lower()
        zh = re.findall(r"[\u4e00-\u9fff]", text)
        words = re.findall(r"[a-z0-9]+", text)
        return zh + words

    def _lexical_score(self, query: str, text: str) -> float:
        q = self._tokens(query)
        if not q:
            return 0.0
        t = set(self._tokens(text))
        hit = sum(1 for token in q if token in t)
        return hit / len(q)

    async def retrieve(self, query: str) -> list[dict[str, Any]]:
        embs = await self.embedding_service.embed_texts([query])
        if not embs:
            return []
        query_vec = embs[0].get("embedding", [])

        dense_hits = self.milvus_repo.search_dense(query_vec, top_k=max(self.top_k * 3, 10))
        dense_map = {x["chunk_id"]: x for x in dense_hits}

        chunk_pool = self.sqlite_repo.list_chunks(limit=3000)
        lexical_hits = []
        for chunk in chunk_pool:
            score = self._lexical_score(query, chunk.get("chunk_text", ""))
            if score <= 0:
                continue
            lexical_hits.append({**chunk, "bm25_score": score})
        lexical_hits.sort(key=lambda x: x["bm25_score"], reverse=True)
        lexical_hits = lexical_hits[: max(self.top_k * 3, 10)]

        max_dense = max([x.get("dense_score", 0.0) for x in dense_hits], default=1.0)
        max_bm25 = max([x.get("bm25_score", 0.0) for x in lexical_hits], default=1.0)

        merged: dict[str, dict[str, Any]] = {}
        for hit in dense_hits:
            cid = hit["chunk_id"]
            dense_norm = hit.get("dense_score", 0.0) / (max_dense or 1.0)
            merged[cid] = {
                **hit,
                "dense_norm": dense_norm,
                "bm25_norm": 0.0,
            }

        for hit in lexical_hits:
            cid = hit["id"]
            bm25_norm = hit.get("bm25_score", 0.0) / (max_bm25 or 1.0)
            if cid not in merged:
                merged[cid] = {
                    "chunk_id": hit["id"],
                    "file_id": hit.get("file_id", ""),
                    "file_name": "",
                    "page": hit.get("page", 0),
                    "paragraph_id": hit.get("paragraph_id", ""),
                    "block_type": hit.get("block_type", "text"),
                    "chunk_text": hit.get("chunk_text", ""),
                    "dense_score": 0.0,
                    "dense_norm": 0.0,
                    "bm25_norm": bm25_norm,
                }
            else:
                merged[cid]["bm25_norm"] = bm25_norm

        out = []
        for item in merged.values():
            fused = self.dense_weight * item.get("dense_norm", 0.0) + self.bm25_weight * item.get("bm25_norm", 0.0)
            item["fused_score"] = fused
            out.append(item)

        out.sort(key=lambda x: x.get("fused_score", 0.0), reverse=True)
        return out[: self.top_k]
