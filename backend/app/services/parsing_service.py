from __future__ import annotations

import html
import re
import uuid
from typing import Any


class ParsingService:
    IGNORE_LABELS = {
        "number",
        "footnote",
        "header",
        "header_image",
        "footer",
        "footer_image",
        "aside_text",
    }
    TITLE_LABELS = {"title", "paragraph_title", "section_title", "chapter_title", "doc_title"}
    TABLE_LABELS = {"table", "table_title", "table_caption", "table_header", "table_body"}
    FIGURE_LABELS = {"figure", "image", "chart", "picture", "figure_caption"}
    CAPTION_LABELS = {"caption", "figure_caption", "table_caption"}
    TEXT_KEYS = ("text", "block_content", "content", "markdown", "md", "value")
    NOISE_EXACT_TEXTS = {
        "number",
        "footnote",
        "header",
        "header_image",
        "footer",
        "footer_image",
        "aside_text",
        "powered by tcpdf (www.tcpdf.org)",
        "powered by tcpdf",
    }
    IMAGE_URL_RE = re.compile(r"https?://\S+\.(?:png|jpg|jpeg|webp|gif|bmp)(?:\?\S+)?", re.IGNORECASE)
    MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*]\(([^)]+)\)")

    @staticmethod
    def _normalize_label(raw_label: str) -> tuple[str, str]:
        label = re.sub(r"[\s\-]+", "_", (raw_label or "text").strip().lower())
        if label in ParsingService.IGNORE_LABELS:
            return "ignore", label
        if label in ParsingService.TITLE_LABELS:
            return "title", label
        if label in ParsingService.TABLE_LABELS:
            return "table", label
        if label in ParsingService.FIGURE_LABELS:
            return "figure", label
        if label in ParsingService.CAPTION_LABELS:
            return "caption", label
        if label in {"list", "list_item", "bullet"}:
            return "list", label
        return "text", label

    @staticmethod
    def _is_noise_text(text: str) -> bool:
        s = (text or "").strip().lower()
        if not s:
            return True
        if s in ParsingService.NOISE_EXACT_TEXTS:
            return True
        if "powered by tcpdf" in s:
            return True
        if re.fullmatch(r"(header|footer|footnote|aside_text|header_image|footer_image|number)", s):
            return True
        return False

    @staticmethod
    def _clean_text(text: str, block_type: str) -> str:
        if not text:
            return ""
        s = html.unescape(str(text))

        # 表格块优先保留原始 HTML，方便前端直接渲染。
        if block_type == "table":
            s = re.sub(r"\r\n?", "\n", s)
            s = re.sub(r"\n{3,}", "\n\n", s)
            s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
            return s.strip()

        # 对 HTML/富文本输出做清洗，避免正文中出现大量 <> 标签。
        if "<" in s and ">" in s:
            s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
            s = re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", s, flags=re.IGNORECASE)
            s = re.sub(r"<[^>]+>", " ", s)

        s = s.replace("\u3000", " ")
        s = s.replace("\xa0", " ")
        s = re.sub(r"[ \t]+", " ", s)
        s = re.sub(r"\n{3,}", "\n\n", s)
        s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
        s = s.strip()

        return s

    @staticmethod
    def _looks_like_base64_image(text: str) -> bool:
        s = (text or "").strip()
        if len(s) < 256:
            return False
        if s.startswith("data:image/"):
            return True
        if s.startswith("/9j/") or s.startswith("iVBORw0KGgo") or s.startswith("R0lGOD"):
            return True
        # 粗略检测：仅 base64 字符且长度较长。
        return bool(re.fullmatch(r"[A-Za-z0-9+/=\s]+", s))

    @staticmethod
    def _infer_block_type_by_content(raw_text: str, block_type: str, label: str) -> tuple[str, str]:
        if block_type in {"table", "figure"}:
            return block_type, label
        s = (raw_text or "").strip()
        s_l = s.lower()
        if "<table" in s_l or ("<tr" in s_l and "<td" in s_l):
            return "table", "table_html"
        if "<img" in s_l or ParsingService.MARKDOWN_IMAGE_RE.search(s):
            return "figure", "image_html"
        if ParsingService.IMAGE_URL_RE.search(s) or ParsingService._looks_like_base64_image(s):
            return "figure", "image_content"
        return block_type, label

    @staticmethod
    def _extract_page_from_obj(item: dict[str, Any], default_page: int | None = None) -> int | None:
        for key in (
            "page",
            "page_id",
            "page_idx",
            "pageIndex",
            "page_no",
            "pageNum",
            "page_number",
            "pageNumber",
            "page_index",
        ):
            val = item.get(key)
            if isinstance(val, int):
                return max(val, 1)
            if isinstance(val, str) and val.isdigit():
                return max(int(val), 1)
        return default_page

    @staticmethod
    def _extract_bbox_from_list(bbox: list[Any] | tuple[Any, ...] | None) -> tuple[float, float, float, float]:
        if not bbox:
            return (0.0, 0.0, 0.0, 0.0)
        if len(bbox) >= 8:
            xs = [float(bbox[i]) for i in range(0, 8, 2)]
            ys = [float(bbox[i]) for i in range(1, 8, 2)]
            return (min(xs), min(ys), max(xs), max(ys))
        if len(bbox) >= 4:
            x1, y1, x2, y2 = [float(v) for v in bbox[:4]]
            return (x1, y1, x2, y2)
        return (0.0, 0.0, 0.0, 0.0)

    @staticmethod
    def _extract_text_from_item(item: dict[str, Any]) -> str:
        for key in ParsingService.TEXT_KEYS:
            value = item.get(key)
            if isinstance(value, str):
                return value
            if key == "markdown" and isinstance(value, dict):
                text = value.get("text")
                if isinstance(text, str):
                    return text
        return ""

    @staticmethod
    def _layout_results_from_raw(raw: dict[str, Any]) -> list[Any]:
        if not isinstance(raw, dict):
            return []

        candidates: list[Any] = [raw]
        for key in ("result", "data"):
            node = raw.get(key)
            if isinstance(node, dict):
                candidates.append(node)

        for node in candidates:
            layout_results = node.get("layoutParsingResults")
            if isinstance(layout_results, list):
                return layout_results
        return []

    def _extract_blocks_from_layout_results(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        layout_results = self._layout_results_from_raw(raw)
        if not layout_results:
            return []

        blocks: list[dict[str, Any]] = []

        for page_idx, page_item in enumerate(layout_results, start=1):
            if not isinstance(page_item, dict):
                continue

            page_no = self._extract_page_from_obj(page_item, page_idx) or page_idx
            pruned = page_item.get("prunedResult") or {}
            parsing_list = pruned.get("parsing_res_list") or pruned.get("parsingResList") or []
            page_blocks_before = len(blocks)

            if isinstance(parsing_list, list) and parsing_list:
                for blk in parsing_list:
                    if not isinstance(blk, dict):
                        continue

                    raw_label = str(blk.get("block_label") or blk.get("label") or "text")
                    block_type, label = self._normalize_label(raw_label)
                    if block_type == "ignore":
                        continue

                    raw_text = str(blk.get("block_content") or blk.get("text") or "")
                    block_type, label = self._infer_block_type_by_content(raw_text, block_type, label)
                    text = self._clean_text(raw_text, block_type)
                    if self._is_noise_text(text):
                        continue

                    page = self._extract_page_from_obj(blk, page_no) or page_no
                    x1, y1, x2, y2 = self._extract_bbox_from_list(blk.get("block_bbox"))
                    order = blk.get("block_order")
                    if not isinstance(order, int):
                        order = blk.get("block_id") if isinstance(blk.get("block_id"), int) else 0

                    blocks.append(
                        {
                            "id": str(uuid.uuid4()),
                            "page": int(page),
                            "block_type": block_type,
                            "layout_label": label,
                            "order": int(order),
                            "x1": x1,
                            "y1": y1,
                            "x2": x2,
                            "y2": y2,
                            "text": text,
                            "source": "layout_parsing_res_list",
                            "raw": blk,
                        }
                    )

            # 没有有效 block 时，退回 page 级 markdown 文本。
            if len(blocks) > page_blocks_before:
                continue

            markdown = page_item.get("markdown")
            if not isinstance(markdown, dict) and isinstance(pruned.get("markdown"), dict):
                markdown = pruned.get("markdown")
            if isinstance(markdown, dict):
                text = self._clean_text(str(markdown.get("text") or ""), "text")
                if not self._is_noise_text(text):
                    blocks.append(
                        {
                            "id": str(uuid.uuid4()),
                            "page": page_no,
                            "block_type": "text",
                            "layout_label": "markdown",
                            "order": 0,
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 0.0,
                            "y2": 0.0,
                            "text": text,
                            "source": "layout_markdown",
                            "raw": markdown,
                        }
                    )

        return blocks

    @staticmethod
    def _extract_page_from_key(key: Any, default_page: int | None = None) -> int | None:
        if not isinstance(key, str):
            return default_page
        key_s = key.strip().lower()
        patterns = [
            r"^page[_\- ]?(\d+)$",
            r"^p[_\- ]?(\d+)$",
            r"^(\d+)$",
            r".*page[_\- ]?(\d+).*$",
            r"^第(\d+)页$",
        ]
        for pat in patterns:
            m = re.match(pat, key_s, flags=re.IGNORECASE)
            if m:
                n = int(m.group(1))
                if n > 0:
                    return n
        return default_page

    @staticmethod
    def _iter_dict_nodes_with_page(obj: Any, inherited_page: int | None = None):
        if isinstance(obj, dict):
            current_page = ParsingService._extract_page_from_obj(obj, inherited_page)
            yield obj, current_page
            for key, value in obj.items():
                key_page = ParsingService._extract_page_from_key(key, current_page)
                yield from ParsingService._iter_dict_nodes_with_page(value, key_page)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    yield from ParsingService._iter_dict_nodes_with_page(item, inherited_page)

    @staticmethod
    def _is_probably_block(item: dict[str, Any]) -> bool:
        keys = set(item.keys())
        if keys & {"block_label", "block_type", "label", "type"}:
            return True
        if keys & {"text", "block_content", "content", "markdown"}:
            return True
        if keys & {"bbox", "box", "rect", "block_bbox"}:
            return True
        return False

    def _extract_blocks_generic(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        data = raw.get("data")
        if data is None:
            data = raw.get("result", raw)

        blocks: list[dict[str, Any]] = []
        for item, parent_page in self._iter_dict_nodes_with_page(data, None):
            if not isinstance(item, dict):
                continue
            if not self._is_probably_block(item):
                continue
            raw_label = str(item.get("type") or item.get("block_type") or item.get("label") or "text")
            block_type, label = self._normalize_label(raw_label)
            if block_type == "ignore":
                continue

            raw_text = self._extract_text_from_item(item)
            block_type, label = self._infer_block_type_by_content(raw_text, block_type, label)
            text = self._clean_text(raw_text, block_type)
            if self._is_noise_text(text):
                continue

            page = self._extract_page_from_obj(item, parent_page) or 1
            bbox = item.get("bbox") or item.get("box") or item.get("rect") or item.get("block_bbox")
            x1, y1, x2, y2 = self._extract_bbox_from_list(bbox if isinstance(bbox, (list, tuple)) else None)

            blocks.append(
                {
                    "id": str(uuid.uuid4()),
                    "page": int(page),
                    "block_type": block_type,
                    "layout_label": label,
                    "order": int(item.get("order") or item.get("block_order") or 0),
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "text": text,
                    "source": "generic_fallback",
                    "raw": item,
                }
            )
        return blocks

    @staticmethod
    def _dedup_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[int, str, str]] = set()
        out: list[dict[str, Any]] = []
        for b in blocks:
            key = (int(b.get("page", 1)), str(b.get("block_type", "text")), str(b.get("text", ""))[:300])
            if key in seen:
                continue
            seen.add(key)
            out.append(b)
        return out

    def normalize_layout_result(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        specific_blocks = self._extract_blocks_from_layout_results(raw)
        if specific_blocks:
            return self._dedup_blocks(specific_blocks)

        generic_blocks = self._extract_blocks_generic(raw)
        return self._dedup_blocks(generic_blocks)

    def filter_header_footer(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # 主过滤已在 normalize 内通过 label 处理，这里仅保底。
        filtered: list[dict[str, Any]] = []
        for block in blocks:
            bt = str(block.get("block_type", "")).lower()
            label = str(block.get("layout_label", "")).lower()
            if bt in {"ignore"}:
                continue
            if label in self.IGNORE_LABELS:
                continue
            if self._is_noise_text(str(block.get("text", ""))):
                continue
            filtered.append(block)
        return filtered
