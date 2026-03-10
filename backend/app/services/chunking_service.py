from __future__ import annotations

import uuid
from typing import Any

from app.utils.layout_flow import build_logical_units
from app.utils.text_util import semantic_chunk


class ChunkingService:
    def __init__(self, chunk_size: int, overlap: int, min_chunk_chars: int = 600):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_chunk_chars = max(1, min_chunk_chars)

    @staticmethod
    def _is_text_like(unit_type: str) -> bool:
        return unit_type in {"text", "list"}

    @staticmethod
    def _dedupe_keep_order(values: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for v in values:
            s = str(v or "").strip()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

    @staticmethod
    def _join_non_empty(parts: list[str]) -> str:
        return "\n\n".join([str(x).strip() for x in parts if str(x or "").strip()])

    def _unit_len(self, unit: dict[str, Any]) -> int:
        return len(str(unit.get("plain_text", "")).strip())

    def _merge_two_units(self, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        left_types = [str(x) for x in list(left.get("unit_types", [left.get("unit_type", "text")]))]
        right_types = [str(x) for x in list(right.get("unit_types", [right.get("unit_type", "text")]))]
        merged_types = self._dedupe_keep_order(left_types + right_types)
        merged_source_ids = self._dedupe_keep_order(
            [str(x) for x in list(left.get("source_block_ids", []) or []) + list(right.get("source_block_ids", []) or [])]
        )
        merged_caption = self._join_non_empty([str(left.get("caption", "") or ""), str(right.get("caption", "") or "")])
        merged_figure_type = self._join_non_empty(
            [str(left.get("figure_type", "") or ""), str(right.get("figure_type", "") or "")]
        )
        merged_figure_summary = self._join_non_empty(
            [str(left.get("figure_summary", "") or ""), str(right.get("figure_summary", "") or "")]
        )
        merged_section = str(left.get("section_title", "") or "") or str(right.get("section_title", "") or "")
        return {
            "page": int(left.get("page", 1)),
            "unit_type": str(left.get("unit_type", "text")),
            "markdown": self._join_non_empty([str(left.get("markdown", "")), str(right.get("markdown", ""))]),
            "plain_text": self._join_non_empty([str(left.get("plain_text", "")), str(right.get("plain_text", ""))]),
            "caption": merged_caption,
            "figure_type": merged_figure_type,
            "figure_summary": merged_figure_summary,
            "section_title": merged_section,
            "source_block_ids": merged_source_ids,
            "unit_types": merged_types or [str(left.get("unit_type", "text"))],
        }

    def _merge_tiny_units(self, units: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(units) <= 1:
            return units

        work: list[dict[str, Any]] = [dict(u) for u in units]
        i = 0
        while i < len(work):
            cur = work[i]
            cur_len = self._unit_len(cur)
            if cur_len >= self.min_chunk_chars or len(work) == 1:
                i += 1
                continue

            prev_idx = i - 1 if i > 0 else None
            next_idx = i + 1 if i + 1 < len(work) else None
            if prev_idx is None and next_idx is None:
                i += 1
                continue

            cur_page = int(cur.get("page", 1))
            cur_section = str(cur.get("section_title", "") or "")

            def score(idx: int | None) -> float:
                if idx is None:
                    return -1e9
                neighbor = work[idx]
                s = 0.0
                n_page = int(neighbor.get("page", 1))
                n_section = str(neighbor.get("section_title", "") or "")
                if n_page == cur_page:
                    s += 6.0
                elif abs(n_page - cur_page) == 1:
                    s += 2.0
                if cur_section and n_section == cur_section:
                    s += 3.0
                if str(neighbor.get("unit_type", "text")) == "text":
                    s += 1.0
                s -= abs(self._unit_len(neighbor) - self.min_chunk_chars) / max(float(self.min_chunk_chars), 1.0)
                return s

            # 优先合并到相邻且语义更近的一侧。
            target_idx = prev_idx if score(prev_idx) >= score(next_idx) else next_idx
            if target_idx is None:
                i += 1
                continue

            if target_idx < i:
                merged = self._merge_two_units(work[target_idx], cur)
                work[target_idx] = merged
                del work[i]
                i = max(target_idx - 1, 0)
            else:
                merged = self._merge_two_units(cur, work[target_idx])
                work[i] = merged
                del work[target_idx]
            # 继续在当前位置检查，直到该块不再过小。
        return work

    def _coarsen_parts(self, parts: list[str]) -> list[str]:
        if len(parts) <= 1:
            return [p for p in parts if str(p or "").strip()]

        merged: list[str] = []
        buf = ""
        for raw in parts:
            part = str(raw or "").strip()
            if not part:
                continue
            if not buf:
                buf = part
                continue
            if len(buf) < self.min_chunk_chars:
                buf = f"{buf}\n{part}"
                continue
            merged.append(buf)
            buf = part

        if buf:
            if merged and len(buf) < self.min_chunk_chars:
                merged[-1] = f"{merged[-1]}\n{buf}"
            else:
                merged.append(buf)

        return merged or [p for p in parts if str(p or "").strip()]

    def _merge_units_for_chunking(self, units: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        i = 0
        n = len(units)

        while i < n:
            u = units[i]
            unit_type = str(u.get("unit_type", "text"))
            page = int(u.get("page", 1))
            if unit_type == "title":
                i += 1
                continue

            # 图/表块：自动吸附前后邻近正文，避免只剩标题。
            if unit_type in {"table", "figure"}:
                md_parts: list[str] = []
                plain_parts: list[str] = []
                source_ids: list[str] = []
                unit_types: list[str] = [unit_type]

                if merged and int(merged[-1].get("page", 1)) == page and str(merged[-1].get("unit_type")) == "text":
                    prev = merged.pop()
                    md_parts.append(str(prev.get("markdown", "")).strip())
                    plain_parts.append(str(prev.get("plain_text", "")).strip())
                    source_ids.extend(list(prev.get("source_block_ids", []) or []))
                    unit_types.append("text")

                md_parts.append(str(u.get("markdown", "")).strip())
                plain_parts.append(str(u.get("plain_text", "")).strip())
                source_ids.extend(list(u.get("source_block_ids", []) or []))

                j = i + 1
                absorbed = 0
                while j < n and absorbed < 2:
                    nxt = units[j]
                    nxt_type = str(nxt.get("unit_type", "text"))
                    if int(nxt.get("page", 1)) != page:
                        break
                    if not self._is_text_like(nxt_type):
                        break
                    candidate = str(nxt.get("plain_text", "")).strip()
                    cur_len = len("\n\n".join([x for x in plain_parts if x]))
                    if cur_len + len(candidate) > int(self.chunk_size * 1.6):
                        break
                    md_parts.append(str(nxt.get("markdown", "")).strip())
                    plain_parts.append(candidate)
                    source_ids.extend(list(nxt.get("source_block_ids", []) or []))
                    unit_types.append("text")
                    absorbed += 1
                    j += 1

                merged.append(
                    {
                        "page": page,
                        "unit_type": unit_type,
                        "markdown": "\n\n".join([x for x in md_parts if x]),
                        "plain_text": "\n\n".join([x for x in plain_parts if x]),
                        "caption": str(u.get("caption", "") or ""),
                        "figure_type": str(u.get("figure_type", "") or ""),
                        "figure_summary": str(u.get("figure_summary", "") or ""),
                        "section_title": str(u.get("section_title", "") or ""),
                        "source_block_ids": self._dedupe_keep_order([str(x) for x in source_ids]),
                        "unit_types": self._dedupe_keep_order(unit_types),
                    }
                )
                i = j
                continue

            # 正文块：连续合并到更粗粒度。
            if self._is_text_like(unit_type):
                md_parts = [str(u.get("markdown", "")).strip()]
                plain_parts = [str(u.get("plain_text", "")).strip()]
                source_ids = list(u.get("source_block_ids", []) or [])
                section_title = str(u.get("section_title", "") or "")
                j = i + 1
                while j < n:
                    nxt = units[j]
                    nxt_type = str(nxt.get("unit_type", "text"))
                    if not self._is_text_like(nxt_type):
                        break
                    if int(nxt.get("page", 1)) != page:
                        break
                    nxt_plain = str(nxt.get("plain_text", "")).strip()
                    cur_len = len("\n\n".join([x for x in plain_parts if x]))
                    nxt_section = str(nxt.get("section_title", "") or "")
                    if section_title and nxt_section != section_title and cur_len >= self.min_chunk_chars:
                        break
                    if cur_len + len(nxt_plain) > int(self.chunk_size * 1.6):
                        break
                    md_parts.append(str(nxt.get("markdown", "")).strip())
                    plain_parts.append(nxt_plain)
                    source_ids.extend(list(nxt.get("source_block_ids", []) or []))
                    j += 1

                merged.append(
                    {
                        "page": page,
                        "unit_type": "text",
                        "markdown": "\n\n".join([x for x in md_parts if x]),
                        "plain_text": "\n\n".join([x for x in plain_parts if x]),
                        "caption": "",
                        "figure_type": "",
                        "figure_summary": "",
                        "section_title": section_title,
                        "source_block_ids": self._dedupe_keep_order([str(x) for x in source_ids]),
                        "unit_types": ["text"],
                    }
                )
                i = j
                continue

            merged.append(
                {
                    "page": page,
                    "unit_type": unit_type,
                    "markdown": str(u.get("markdown", "")).strip(),
                    "plain_text": str(u.get("plain_text", "")).strip(),
                    "caption": str(u.get("caption", "") or ""),
                    "figure_type": str(u.get("figure_type", "") or ""),
                    "figure_summary": str(u.get("figure_summary", "") or ""),
                    "section_title": str(u.get("section_title", "") or ""),
                    "source_block_ids": self._dedupe_keep_order([str(x) for x in list(u.get("source_block_ids", []) or [])]),
                    "unit_types": [unit_type],
                }
            )
            i += 1

        return merged

    def build_chunks(self, file_id: str, blocks: list[dict]) -> list[dict]:
        chunks: list[dict] = []
        units = build_logical_units(blocks)
        units = self._merge_units_for_chunking(units)
        units = self._merge_tiny_units(units)
        per_page_idx: dict[int, int] = {}

        for unit in units:
            page = int(unit.get("page", 1))
            unit_type = str(unit.get("unit_type", "text"))
            markdown = str(unit.get("markdown", "")).strip()
            embed_text = str(unit.get("plain_text", markdown)).strip()
            if not embed_text:
                continue

            per_page_idx[page] = per_page_idx.get(page, 0) + 1
            unit_idx = per_page_idx[page]

            if unit_type in {"table", "figure"}:
                # 图表默认保持为单块，但超长时仍按 chunk_size 兜底切分，避免后续入库失败。
                if len(embed_text) > int(self.chunk_size * 1.6):
                    parts = semantic_chunk(embed_text, chunk_size=self.chunk_size, overlap=self.overlap) or [embed_text]
                else:
                    parts = [embed_text]
            else:
                parts = semantic_chunk(embed_text, chunk_size=self.chunk_size, overlap=self.overlap) or [embed_text]
                parts = self._coarsen_parts(parts)

            for idx, part in enumerate(parts, start=1):
                chunks.append(
                    {
                        "id": str(uuid.uuid4()),
                        "file_id": file_id,
                        "page": page,
                        "paragraph_id": f"p{page}_u{unit_idx}_{idx}",
                        "block_type": unit_type,
                        "chunk_index": idx,
                        "chunk_text": part,
                        "source_offset": 0,
                        "metadata": {
                            "page": page,
                            "block_type": unit_type,
                            "unit_types": unit.get("unit_types", [unit_type]),
                            "section_title": unit.get("section_title", ""),
                            "caption": unit.get("caption", ""),
                            "source_block_ids": unit.get("source_block_ids", []),
                            "markdown": markdown,
                            "figure_type": unit.get("figure_type", ""),
                            "figure_summary": unit.get("figure_summary", ""),
                        },
                    }
                )
        return chunks
