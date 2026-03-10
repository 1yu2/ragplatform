from __future__ import annotations

import html
import re
from collections import defaultdict
from typing import Any

NOISE_BLOCK_TYPES = {
    "ignore",
    "number",
    "footnote",
    "header",
    "header_image",
    "footer",
    "footer_image",
    "aside_text",
}

NOISE_TEXTS = {
    "number",
    "footnote",
    "header",
    "header_image",
    "footer",
    "footer_image",
    "aside_text",
}

TABLE_CAPTION_RE = re.compile(r"^\s*(表\s*\d+|表[一二三四五六七八九十百]+|table\s*\d+)", re.IGNORECASE)
FIGURE_CAPTION_RE = re.compile(r"^\s*(图\s*\d+|图[一二三四五六七八九十百]+|figure\s*\d+)", re.IGNORECASE)
MARKDOWN_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
IMAGE_URL_RE = re.compile(r"https?://\S+\.(?:png|jpg|jpeg|webp|gif|bmp)(?:\?\S+)?", re.IGNORECASE)
IMG_TAG_RE = re.compile(r"<img[^>]+src=['\"]([^'\"]+)['\"]", re.IGNORECASE)
MD_IMG_RE = re.compile(r"!\[[^\]]*]\(([^)]+)\)")


def _normalize_text(text: str) -> str:
    s = html.unescape(str(text or ""))
    # 清理 OCR/markdown 中常见的 latex 脚注噪声：$ ^{1} $ -> [1]
    s = re.sub(r"\$\s*\^\{\s*(\d+)\s*\}\s*\$", r"[\1]", s)
    s = re.sub(r"\$\s*\^\s*(\d+)\s*\$", r"[\1]", s)
    s = re.sub(r"\$\s*\^\{\s*([^}]+)\s*\}\s*\$", r"[\1]", s)
    s = s.replace("\u3000", " ").replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s+([，。；：！？,.!?])", r"\1", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _is_noise_text(text: str) -> bool:
    s = (text or "").strip().lower()
    if not s:
        return True
    if s in NOISE_TEXTS:
        return True
    if "powered by tcpdf" in s:
        return True
    return False


def sort_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(b: dict[str, Any]):
        return (
            int(b.get("page", 1)),
            float(b.get("y1", 0.0)),
            float(b.get("x1", 0.0)),
            int(b.get("order", 0)),
            str(b.get("id", "")),
        )

    return sorted(blocks, key=sort_key)


def _caption_kind(text: str) -> str | None:
    s = (text or "").strip()
    if not s:
        return None
    if TABLE_CAPTION_RE.search(s):
        return "table"
    if FIGURE_CAPTION_RE.search(s):
        return "figure"
    return None


def _collect_neighbor_texts(enriched: list[dict[str, Any]], idx: int, page: int, max_each_side: int = 2) -> list[str]:
    before: list[str] = []
    after: list[str] = []

    for j in range(idx - 1, -1, -1):
        b = enriched[j]
        if int(b.get("page", 1)) != page:
            break
        if str(b.get("kind")) == "text":
            t = _normalize_text(str(b.get("text", "")))
            if t:
                before.append(t)
                if len(before) >= max_each_side:
                    break

    for j in range(idx + 1, len(enriched)):
        b = enriched[j]
        if int(b.get("page", 1)) != page:
            break
        if str(b.get("kind")) == "text":
            t = _normalize_text(str(b.get("text", "")))
            if t:
                after.append(t)
                if len(after) >= max_each_side:
                    break

    before.reverse()
    return before + after


def _infer_figure_type(caption: str, raw_text: str, neighbor_texts: list[str]) -> str:
    s = " ".join([caption or "", raw_text or "", " ".join(neighbor_texts)]).lower()
    if any(k in s for k in ["同比", "环比", "增速", "占比", "亿元", "%", "曲线", "柱状", "饼图", "图表", "指标"]):
        return "图表"
    if any(k in s for k in ["流程", "步骤", "架构", "拓扑", "框图", "示意"]):
        return "流程/结构图"
    if any(k in s for k in ["地图", "区域", "分布"]):
        return "地图"
    return "图片/插图"


def _build_figure_summary(caption: str, neighbor_texts: list[str]) -> str:
    _ = caption
    neighbor = [_normalize_text(t) for t in neighbor_texts if _normalize_text(t)]
    summary = "；".join(neighbor[:2]).strip("； ")
    return summary


def _extract_figure_self_summary(raw_text: str, caption: str) -> str:
    s = _normalize_text(_strip_html_tags(str(raw_text or "")))
    if not s:
        return ""
    if _is_base64_image(s):
        return ""
    c = _normalize_text(caption)
    if c and s.startswith(c):
        s = _normalize_text(s[len(c) :])
    if s and s != c and len(s) >= 12:
        return s
    return ""


def _is_base64_image(text: str) -> bool:
    s = (text or "").strip()
    if len(s) < 256:
        return False
    if s.startswith("data:image/") or s.startswith("/9j/") or s.startswith("iVBORw0KGgo") or s.startswith("R0lGOD"):
        return True
    return bool(re.fullmatch(r"[A-Za-z0-9+/=\s]+", s))


def infer_kind(block: dict[str, Any]) -> str:
    block_type = str(block.get("block_type", "text")).lower()
    text = str(block.get("text", "") or "")
    t = text.lower()
    if block_type in NOISE_BLOCK_TYPES:
        return "noise"
    if _is_noise_text(text):
        return "noise"
    if block_type == "title":
        return "title"
    if block_type == "caption":
        return "caption"
    if block_type == "table" or "<table" in t or ("<tr" in t and "<td" in t):
        return "table"
    if block_type == "figure" or "<img" in t or MD_IMG_RE.search(text) or IMAGE_URL_RE.search(text) or _is_base64_image(text):
        return "figure"
    if _caption_kind(text):
        return "caption"
    return "text"


def _strip_html_tags(text: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    s = re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", " ", s)
    return _normalize_text(s)


def _cell_text(cell_html: str) -> str:
    s = html.unescape(cell_html)
    s = _strip_html_tags(s)
    return s.replace("|", r"\|")


def _rows_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    col_n = max(len(r) for r in rows)
    if col_n <= 0:
        return ""
    normalized = [r + [""] * (col_n - len(r)) for r in rows]
    header = normalized[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * col_n) + " |",
    ]
    for row in normalized[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def html_table_to_markdown(text: str) -> str:
    s = str(text or "")
    row_html_list = re.findall(r"<tr[^>]*>(.*?)</tr>", s, flags=re.IGNORECASE | re.DOTALL)
    if not row_html_list:
        return ""
    rows: list[list[str]] = []
    for row_html in row_html_list:
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, flags=re.IGNORECASE | re.DOTALL)
        if not cells:
            continue
        rows.append([_cell_text(c) for c in cells])
    return _rows_to_markdown(rows)


def _plain_table_to_markdown(text: str) -> str:
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    if not lines:
        return ""
    if any("|" in ln for ln in lines):
        # 看起来已是 markdown table，尽量原样保留。
        normalized = [ln for ln in lines if not MARKDOWN_TABLE_SEP_RE.match(ln)]
        return "\n".join(normalized if normalized else lines)

    def tokenize_row(line: str) -> list[str]:
        s = line.strip()
        if not s:
            return []
        if "\t" in s:
            return [x.strip().replace("|", r"\|") for x in s.split("\t") if x.strip()]
        # 优先多空格切分（OCR 常见列间隔）
        if re.search(r"\s{2,}", s):
            cells = [x.strip().replace("|", r"\|") for x in re.split(r"\s{2,}", s) if x.strip()]
            if len(cells) >= 2:
                return cells
        # 中文表通常单元内部无空格，回退到单空格切分。
        return [x.strip().replace("|", r"\|") for x in re.split(r"\s+", s) if x.strip()]

    rows: list[list[str]] = []
    for ln in lines:
        cells = tokenize_row(ln)
        if len(cells) >= 2:
            rows.append(cells)

    # 如果至少有多列表，单列行也补齐进来，避免行丢失。
    if rows:
        max_col = max(len(r) for r in rows)
        for ln in lines:
            cells = tokenize_row(ln)
            if len(cells) == 1:
                rows.append([cells[0]] + [""] * (max_col - 1))
    return _rows_to_markdown(rows)


def table_to_markdown(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    if "<table" in s.lower():
        md = html_table_to_markdown(s)
        if md:
            return md
    md2 = _plain_table_to_markdown(_strip_html_tags(s))
    if md2:
        return md2
    return _normalize_text(_strip_html_tags(s))


def figure_to_markdown(text: str, caption: str = "") -> str:
    s = str(text or "").strip()
    src = ""
    if s.startswith("data:image/"):
        src = s
    if not src:
        m = MD_IMG_RE.search(s)
        if m:
            src = m.group(1).strip()
    if not src:
        m = IMG_TAG_RE.search(s)
        if m:
            src = m.group(1).strip()
    if not src:
        m = IMAGE_URL_RE.search(s)
        if m:
            src = m.group(0)
    if not src and _is_base64_image(s):
        src = f"data:image/jpeg;base64,{s}"

    alt = caption.strip() if caption.strip() else "图片"
    if src:
        return f"![{alt}]({src})"
    return ""


def build_logical_units(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sort_blocks(blocks)
    # 过滤噪声，统一 kind
    enriched: list[dict[str, Any]] = []
    for b in ordered:
        text = _normalize_text(str(b.get("text", "") or ""))
        kind = infer_kind({**b, "text": text})
        if kind == "noise":
            continue
        enriched.append({**b, "text": text, "kind": kind})

    used_caption_idx: set[int] = set()
    units: list[dict[str, Any]] = []
    current_title = ""

    for idx, block in enumerate(enriched):
        if idx in used_caption_idx:
            continue
        kind = str(block.get("kind"))
        page = int(block.get("page", 1))
        text = str(block.get("text", "")).strip()
        if not text and kind != "figure":
            continue

        if kind == "title":
            current_title = text
            md = text if text.startswith("#") else f"## {text}"
            units.append(
                {
                    "page": page,
                    "unit_type": "title",
                    "markdown": md,
                    "plain_text": text,
                    "caption": "",
                    "section_title": current_title,
                    "source_block_ids": [str(block.get("id", ""))],
                    "order_anchor": idx,
                }
            )
            continue

        if kind == "table":
            caption = ""
            caption_idx = None
            # 表题在上：优先找同页最近的上方 caption
            for j in range(idx - 1, -1, -1):
                c = enriched[j]
                if j in used_caption_idx or int(c.get("page", 1)) != page or c.get("kind") != "caption":
                    continue
                if float(c.get("y1", 0.0)) <= float(block.get("y1", 0.0)):
                    cap_text = str(c.get("text", "")).strip()
                    cap_kind = _caption_kind(cap_text)
                    if cap_kind in {"table", None}:
                        caption = cap_text
                        caption_idx = j
                        used_caption_idx.add(j)
                        break

            table_md = table_to_markdown(text)
            md_parts = []
            if caption:
                md_parts.append(f"**{caption}**")
            md_parts.append(table_md if table_md else text)
            md = "\n\n".join([p for p in md_parts if p]).strip()
            embed_text = md
            if current_title:
                embed_text = f"{current_title}\n\n{md}"

            source_ids = [str(block.get("id", ""))]
            if caption_idx is not None:
                source_ids.insert(0, str(enriched[caption_idx].get("id", "")))

            units.append(
                {
                    "page": page,
                    "unit_type": "table",
                    "markdown": md,
                    "plain_text": embed_text,
                    "caption": caption,
                    "section_title": current_title,
                    "source_block_ids": source_ids,
                    "order_anchor": idx if caption_idx is None else min(idx, caption_idx),
                }
            )
            continue

        if kind == "figure":
            caption = ""
            caption_idx = None
            # 图题在下：优先找同页最近的下方 caption
            for j in range(idx + 1, len(enriched)):
                c = enriched[j]
                if j in used_caption_idx or int(c.get("page", 1)) != page or c.get("kind") != "caption":
                    continue
                if float(c.get("y1", 0.0)) >= float(block.get("y1", 0.0)):
                    cap_text = str(c.get("text", "")).strip()
                    cap_kind = _caption_kind(cap_text)
                    if cap_kind in {"figure", None}:
                        caption = cap_text
                        caption_idx = j
                        used_caption_idx.add(j)
                        break

            base_md = figure_to_markdown(text, caption="")
            neighbor_texts = _collect_neighbor_texts(enriched, idx, page, max_each_side=2)
            figure_type = _infer_figure_type(caption=caption, raw_text=text, neighbor_texts=neighbor_texts)
            figure_summary = _extract_figure_self_summary(raw_text=text, caption=caption)
            display_caption = caption.strip() if caption.strip() else "图片"

            md_parts = [p for p in [base_md, display_caption] if p]
            if figure_summary:
                md_parts.append(f"> 说明：{figure_summary}")
            md = "\n\n".join([p for p in md_parts if p]).strip()

            embed_parts = [display_caption]
            if figure_summary:
                embed_parts.append(f"说明：{figure_summary}")
            embed_text = "\n\n".join(embed_parts).strip()
            if current_title:
                embed_text = f"{current_title}\n\n{embed_text}"

            source_ids = [str(block.get("id", ""))]
            if caption_idx is not None:
                source_ids.append(str(enriched[caption_idx].get("id", "")))

            units.append(
                {
                    "page": page,
                    "unit_type": "figure",
                    "markdown": md,
                    "plain_text": embed_text,
                    "caption": caption,
                    "figure_type": figure_type,
                    "figure_summary": figure_summary,
                    "neighbor_texts": neighbor_texts,
                    "section_title": current_title,
                    "source_block_ids": source_ids,
                    "order_anchor": idx,
                }
            )
            continue

        if kind == "caption":
            # 若图/表题紧邻图表单元，则不单独落一个 caption 单元，避免重复。
            near_visual = False
            for j in (idx - 1, idx + 1):
                if j < 0 or j >= len(enriched):
                    continue
                if int(enriched[j].get("page", 1)) != page:
                    continue
                if enriched[j].get("kind") in {"table", "figure"}:
                    near_visual = True
                    break
            if near_visual:
                continue

            cap_kind = _caption_kind(text)
            if cap_kind == "figure":
                # 仅有图题无图块时，不创建伪 figure，避免生成无价值“小块”。
                # 作为普通文本与后续正文合并。
                md = text
                embed_text = md if not current_title else f"{current_title}\n\n{md}"
                units.append(
                    {
                        "page": page,
                        "unit_type": "text",
                        "markdown": md,
                        "plain_text": embed_text,
                        "caption": text,
                        "section_title": current_title,
                        "source_block_ids": [str(block.get("id", ""))],
                        "order_anchor": idx,
                    }
                )
                continue

            # 被独立 caption 落单时保留为 text，避免信息丢失。
            md = f"*{text}*"
            embed_text = md if not current_title else f"{current_title}\n\n{md}"
            units.append(
                {
                    "page": page,
                    "unit_type": "text",
                    "markdown": md,
                    "plain_text": embed_text,
                    "caption": text,
                    "section_title": current_title,
                    "source_block_ids": [str(block.get("id", ""))],
                    "order_anchor": idx,
                }
            )
            continue

        # 常规正文
        md = text
        embed_text = md if not current_title else f"{current_title}\n\n{md}"
        units.append(
            {
                "page": page,
                "unit_type": "text",
                "markdown": md,
                "plain_text": embed_text,
                "caption": "",
                "section_title": current_title,
                "source_block_ids": [str(block.get("id", ""))],
                "order_anchor": idx,
            }
        )

    return sorted(units, key=lambda u: (int(u["page"]), int(u.get("order_anchor", 0))))


def build_markdown_pages(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_page: dict[int, list[str]] = defaultdict(list)
    for unit in sorted(units, key=lambda u: (int(u["page"]), int(u.get("order_anchor", 0)))):
        md = str(unit.get("markdown", "")).strip()
        if md:
            by_page[int(unit["page"])].append(md)

    pages: list[dict[str, Any]] = []
    for page in sorted(by_page.keys()):
        markdown = "\n\n".join(by_page[page]).strip()
        pages.append(
            {
                "page": page,
                "markdown": markdown,
                "char_count": len(markdown),
                "line_count": len(by_page[page]),
            }
        )
    return pages
