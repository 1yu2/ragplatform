from __future__ import annotations

import base64
import json
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.openai_compat_client import OpenAICompatClient
from app.services.prompt_loader import load_prompt


JSON_BLOCK_RE = re.compile(r"\{.*\}", re.S)


STYLE_ANALYZE_FALLBACK_PROMPT = (
    "你是电商生图风格分析器。你会看到一个新品图和3张爆款参考图。"
    "请先分析每张参考图的场景、灯光、模特姿势、画面氛围，再从中严格选出top1。"
    "然后输出可用于图像生成的风格提示词，提示词中必须体现：场景、灯光、姿势、氛围。"
    "严格返回 JSON，字段必须是 selected_index, style_prompt。"
)


@dataclass
class StyleAnalyzeResult:
    selected_index: int
    style_prompt: str
    raw_text: str


class StyleService:
    """Qwen style analysis using OpenAI-compatible API."""

    def __init__(self) -> None:
        self.client = OpenAICompatClient()

    def analyze_top3(
        self,
        payload: dict[str, Any],
        *,
        new_image_path: str | None = None,
        ref_image_paths: list[str] | None = None,
    ) -> StyleAnalyzeResult:
        instruction = load_prompt("qwen_style_analyze.md", STYLE_ANALYZE_FALLBACK_PROMPT)

        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": instruction,
            },
            {"type": "text", "text": json.dumps(payload, ensure_ascii=False)},
        ]

        if new_image_path:
            try:
                content.append({"type": "text", "text": "新品图："})
                content.append({"type": "image_url", "image_url": {"url": self._to_data_url(new_image_path)}})
            except Exception:
                pass

        for idx, p in enumerate(ref_image_paths or [], start=1):
            try:
                content.append({"type": "text", "text": f"参考图{idx}："})
                content.append({"type": "image_url", "image_url": {"url": self._to_data_url(p)}})
            except Exception:
                continue

        messages = [{"role": "user", "content": content}]

        response = self.client.chat_completion_modelscope(messages=messages, temperature=0.2)
        text = self._extract_text(response)
        if not text:
            return StyleAnalyzeResult(
                selected_index=0,
                style_prompt="",
                raw_text="",
            )

        try:
            data = json.loads(text)
        except Exception:
            m = JSON_BLOCK_RE.search(text)
            if not m:
                return StyleAnalyzeResult(
                    selected_index=0,
                    style_prompt="",
                    raw_text=text,
                )
            try:
                data = json.loads(m.group(0))
            except Exception:
                return StyleAnalyzeResult(
                    selected_index=0,
                    style_prompt="",
                    raw_text=text,
                )

        return StyleAnalyzeResult(
            selected_index=self._to_int(data.get("selected_index", 0)),
            style_prompt=str(data.get("style_prompt", "")),
            raw_text=text,
        )

    @staticmethod
    def _to_int(v: Any) -> int:
        try:
            return int(v)
        except Exception:
            return 0

    @staticmethod
    def _to_data_url(path: str) -> str:
        p = Path(path)
        if not p.exists() or not p.is_file():
            raise RuntimeError(f"image file not found: {path}")
        mime_type = mimetypes.guess_type(str(p))[0] or "image/jpeg"
        b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
        return f"data:{mime_type};base64,{b64}"

    @staticmethod
    def _extract_text(response: Any) -> str:
        if hasattr(response, "model_dump"):
            try:
                obj = response.model_dump()
            except Exception:
                obj = response
        else:
            obj = response

        try:
            choices = obj.get("choices") if isinstance(obj, dict) else None
            if not choices:
                return ""
            msg = choices[0].get("message", {})
            content = msg.get("content")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                texts: list[str] = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        texts.append(str(item.get("text", "")))
                return "\n".join([t for t in texts if t]).strip()
            return ""
        except Exception:
            return ""
