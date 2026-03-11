from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.embedding_payloads import image_embedding_payload_candidates
from app.services.openai_compat_client import OpenAICompatClient

TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


@dataclass
class RetrievedItem:
    product_id: str
    image_path: str
    final_score: float
    dense_score: float
    sparse_score: float
    category: str
    color: str
    style: str
    season: str
    sales_count: int
    description: str


class SearchService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.ai_client = OpenAICompatClient()

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [m.group(0).lower() for m in TOKEN_RE.finditer(text or "")]

    @staticmethod
    def _safe_int(v: Any, default: int = 0) -> int:
        try:
            return int(v)
        except Exception:
            return default

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    @staticmethod
    def _build_doc_text(row: dict[str, str]) -> str:
        parts = [
            row.get("category", ""),
            row.get("color", ""),
            row.get("style", ""),
            row.get("season", ""),
            row.get("description", ""),
        ]
        return " ".join([p for p in parts if p])

    @staticmethod
    def _tf(tokens: list[str]) -> dict[str, int]:
        d: dict[str, int] = {}
        for t in tokens:
            d[t] = d.get(t, 0) + 1
        return d

    @staticmethod
    def _cosine_from_tf(a: dict[str, int], b: dict[str, int]) -> float:
        if not a or not b:
            return 0.0
        dot = 0.0
        for k, va in a.items():
            vb = b.get(k)
            if vb:
                dot += va * vb
        if dot == 0:
            return 0.0
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def _bm25_scores(self, query_tokens: list[str], doc_tokens_list: list[list[str]]) -> list[float]:
        # Simple BM25 with fixed k1/b suitable for MVP debug endpoint.
        k1 = 1.5
        b = 0.75
        N = len(doc_tokens_list)
        if N == 0:
            return []

        doc_lens = [len(toks) for toks in doc_tokens_list]
        avgdl = sum(doc_lens) / N if N > 0 else 0.0

        df: dict[str, int] = {}
        for toks in doc_tokens_list:
            seen = set(toks)
            for t in seen:
                df[t] = df.get(t, 0) + 1

        query_terms = list(dict.fromkeys(query_tokens))

        scores: list[float] = []
        for toks in doc_tokens_list:
            tf = self._tf(toks)
            dl = len(toks)
            score = 0.0
            for term in query_terms:
                n_qi = df.get(term, 0)
                if n_qi == 0:
                    continue
                idf = math.log(1 + (N - n_qi + 0.5) / (n_qi + 0.5))
                f_qi = tf.get(term, 0)
                if f_qi == 0:
                    continue
                denom = f_qi + k1 * (1 - b + b * (dl / avgdl if avgdl else 0.0))
                score += idf * ((f_qi * (k1 + 1)) / denom)
            scores.append(score)
        return scores

    @staticmethod
    def _normalize(scores: list[float]) -> list[float]:
        if not scores:
            return []
        lo = min(scores)
        hi = max(scores)
        if hi - lo < 1e-12:
            return [0.0 for _ in scores]
        return [(s - lo) / (hi - lo) for s in scores]

    def _get_new_row_by_id(self, new_id: str) -> dict[str, str]:
        new_rows = self._read_csv(Path(self.settings.data_new_products_csv_path))
        target: dict[str, str] | None = None
        for r in new_rows:
            if (r.get("new_id") or "") == new_id:
                target = r
                break
        if target is None:
            raise ValueError(f"new_id not found: {new_id}")
        return target

    def _query_text_by_new_row(self, target: dict[str, str]) -> str:
        parts = [
            target.get("category", ""),
            target.get("style", ""),
            target.get("season", ""),
            target.get("prompt_hint", ""),
        ]
        return " ".join([p for p in parts if p]).strip()

    def _dense_scores_from_milvus(self, query_image_path: str, limit: int) -> dict[str, float] | None:
        try:
            if not self.settings.openrouter_api_key:
                return None

            query_vec: list[float] | None = None
            last_err: Exception | None = None
            for payload in image_embedding_payload_candidates([query_image_path]):
                try:
                    emb_resp = self.ai_client.embedding_openrouter(
                        input_data=payload,
                        model=self.settings.openrouter_embedding_model,
                    )
                    query_vec = self._first_embedding_vector(emb_resp)
                    break
                except Exception as e:
                    last_err = e
                    continue

            if query_vec is None:
                if last_err is None:
                    return None
                raise last_err

            from pymilvus import Collection, connections, utility

            connections.connect(alias="default", host=self.settings.milvus_host, port=self.settings.milvus_port)
            if not utility.has_collection(self.settings.milvus_collection):
                return None

            col = Collection(self.settings.milvus_collection)
            col.load()

            search_limit = max(1, int(limit))
            hits = col.search(
                data=[query_vec],
                anns_field="image_vector",
                param={"metric_type": "COSINE", "params": {"ef": 128}},
                limit=search_limit,
                output_fields=["product_id"],
            )

            out: dict[str, float] = {}
            if not hits:
                return out
            for hit in hits[0]:
                pid = ""
                try:
                    entity = getattr(hit, "entity", None)
                    if entity is not None and hasattr(entity, "get"):
                        pid = str(entity.get("product_id") or "")
                except Exception:
                    pid = ""
                if not pid:
                    pid = str(getattr(hit, "id", "") or "")
                if not pid:
                    continue

                score = float(getattr(hit, "distance", 0.0) or 0.0)
                out[pid] = score

            return out
        except Exception:
            return None

    def _first_embedding_vector(self, response: Any) -> list[float]:
        data = response.get("data") if isinstance(response, dict) else getattr(response, "data", None)
        if not isinstance(data, list) or not data:
            raise RuntimeError("invalid embedding response")

        item = data[0]
        vec = item.get("embedding") if isinstance(item, dict) else getattr(item, "embedding", None)
        if not isinstance(vec, list):
            raise RuntimeError("embedding vector missing")

        out = [float(x) for x in vec]
        dim = self.settings.vector_dim
        if len(out) == dim:
            return out
        if len(out) > dim:
            return out[:dim]
        return out + [0.0] * (dim - len(out))

    def search_topk_by_new_id(self, new_id: str, top_k: int | None = None) -> list[RetrievedItem]:
        products = self._read_csv(Path(self.settings.data_products_csv_path))
        if not products:
            return []

        new_row = self._get_new_row_by_id(new_id)
        query_text = self._query_text_by_new_row(new_row)
        query_tokens = self._tokenize(query_text)
        query_tf = self._tf(query_tokens)

        doc_texts = [self._build_doc_text(r) for r in products]
        doc_tokens = [self._tokenize(t) for t in doc_texts]

        sparse_raw = self._bm25_scores(query_tokens, doc_tokens)

        k = top_k if top_k is not None else self.settings.retrieval_top_k
        dense_limit = min(len(products), max(100, int(k) * 50))
        dense_map = self._dense_scores_from_milvus(
            query_image_path=str(new_row.get("image_path", "") or ""),
            limit=dense_limit,
        )

        if dense_map is None:
            dense_raw = [self._cosine_from_tf(query_tf, self._tf(toks)) for toks in doc_tokens]
        else:
            dense_raw = [float(dense_map.get(row.get("product_id", ""), 0.0)) for row in products]

        dense_n = self._normalize(dense_raw)
        sparse_n = self._normalize(sparse_raw)

        dw = self.settings.retrieval_dense_weight
        sw = self.settings.retrieval_sparse_weight

        ranked: list[RetrievedItem] = []
        for i, row in enumerate(products):
            final_score = dw * dense_n[i] + sw * sparse_n[i]
            ranked.append(
                RetrievedItem(
                    product_id=row.get("product_id", ""),
                    image_path=row.get("image_path", ""),
                    final_score=float(final_score),
                    dense_score=float(dense_n[i]),
                    sparse_score=float(sparse_n[i]),
                    category=row.get("category", "unknown"),
                    color=row.get("color", "unknown"),
                    style=row.get("style", "unknown"),
                    season=row.get("season", "unknown"),
                    sales_count=self._safe_int(row.get("sales_count", 0), 0),
                    description=row.get("description", ""),
                )
            )

        ranked.sort(key=lambda x: x.final_score, reverse=True)
        return ranked[: max(1, int(k))]
