from __future__ import annotations

import base64
import binascii
import json
import mimetypes
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from app.core.config import get_settings
from app.services.openai_compat_client import OpenAICompatClient
from app.services.prompt_loader import load_prompt


DATA_URL_RE = re.compile(r"data:image/(?P<subtype>[a-zA-Z0-9.+-]+);base64,(?P<data>[A-Za-z0-9+/=\n\r]+)")
URL_RE = re.compile(r"https?://[^\s)>'\"]+")
BASE64_TEXT_RE = re.compile(r"^[A-Za-z0-9+/=\n\r]+$")


IMAGE_GENERATE_FALLBACK_PROMPT = (
    "你是电商服装主图生成助手。"
    "请基于新品图生成商业级宣传图。"
    "必须保留新品服装本体的颜色、款式、纹理和轮廓，不要更换服装主体。"
    "参考图仅用于学习风格，不要复制具体人物或背景。"
    "画面要求：主体完整、构图简洁、光线自然、背景干净。"
    "目标比例：{aspect_ratio}。最终只输出 1 张图片。"
    "\n\n最终提示词：{final_prompt}"
)


@dataclass
class ImageGenerateResult:
    image_path: str
    mime_type: str
    model: str


class ImageGenerationService:
    """Real image generation via OpenAI-compatible API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = OpenAICompatClient()

    def generate_image(
        self,
        *,
        task_id: str,
        new_image_path: str,
        reference_image_path: str | None,
        final_prompt: str,
        aspect_ratio: str,
    ) -> ImageGenerateResult:
        messages = self._build_messages(
            new_image_path=new_image_path,
            reference_image_path=reference_image_path,
            final_prompt=final_prompt,
            aspect_ratio=aspect_ratio,
        )

        # Most OpenAI-compatible providers support this as chat.completions;
        # if extra_body is unsupported, fall back to plain call.
        try:
            response = self.client.chat_completion_openrouter(
                messages=messages,
                model=self.settings.openrouter_image_model,
                temperature=0.3,
                extra_body={"modalities": ["text", "image"]},
            )
        except Exception:
            response = self.client.chat_completion_openrouter(
                messages=messages,
                model=self.settings.openrouter_image_model,
                temperature=0.3,
            )

        image_bytes, mime_type = self._extract_image_bytes(response)
        output_path = self._save_generated_image(task_id=task_id, image_bytes=image_bytes, mime_type=mime_type)

        return ImageGenerateResult(
            image_path=str(output_path.resolve()),
            mime_type=mime_type,
            model=self.settings.openrouter_image_model,
        )

    def _build_messages(
        self,
        *,
        new_image_path: str,
        reference_image_path: str | None,
        final_prompt: str,
        aspect_ratio: str,
    ) -> list[dict[str, Any]]:
        template = load_prompt("nana_image_generate.md", IMAGE_GENERATE_FALLBACK_PROMPT)
        try:
            text = template.format(aspect_ratio=aspect_ratio, final_prompt=final_prompt)
        except Exception:
            text = f"{IMAGE_GENERATE_FALLBACK_PROMPT.format(aspect_ratio=aspect_ratio, final_prompt=final_prompt)}"

        content: list[dict[str, Any]] = [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": self._to_data_url(new_image_path)}},
        ]

        if reference_image_path:
            content.append({"type": "image_url", "image_url": {"url": self._to_data_url(reference_image_path)}})

        return [{"role": "user", "content": content}]

    @staticmethod
    def _to_data_url(path: str) -> str:
        p = Path(path)
        if not p.exists() or not p.is_file():
            raise RuntimeError(f"image file not found: {path}")

        mime_type = mimetypes.guess_type(str(p))[0] or "image/jpeg"
        b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
        return f"data:{mime_type};base64,{b64}"

    def _extract_image_bytes(self, response: Any) -> tuple[bytes, str]:
        obj = response
        if hasattr(response, "model_dump"):
            try:
                obj = response.model_dump()
            except Exception:
                obj = response

        candidates = list(self._iter_strings(obj))

        # 1) data URLs in any string field
        for text in candidates:
            match = DATA_URL_RE.search(text or "")
            if not match:
                continue
            raw = match.group("data")
            try:
                data = base64.b64decode(raw, validate=True)
            except Exception:
                continue
            mime = f"image/{match.group('subtype').lower()}"
            if data:
                return data, mime

        # 2) raw base64 image chunks
        for text in candidates:
            data = self._decode_if_base64_image(text)
            if data:
                image_bytes, mime = data
                return image_bytes, mime

        # 3) remote URLs
        for text in candidates:
            for url in URL_RE.findall(text or ""):
                data = self._download_image(url)
                if data:
                    return data

        payload_excerpt = json.dumps(obj, ensure_ascii=False)[:1200] if isinstance(obj, dict | list) else str(obj)[:1200]
        raise RuntimeError(f"image bytes not found in model response: {payload_excerpt}")

    @staticmethod
    def _iter_strings(node: Any):
        if node is None:
            return
        if isinstance(node, str):
            yield node
            return
        if isinstance(node, dict):
            for v in node.values():
                yield from ImageGenerationService._iter_strings(v)
            return
        if isinstance(node, list):
            for it in node:
                yield from ImageGenerationService._iter_strings(it)

    def _decode_if_base64_image(self, text: str) -> tuple[bytes, str] | None:
        if not text:
            return None
        s = text.strip()
        if len(s) < 800:
            return None
        if not BASE64_TEXT_RE.match(s):
            return None

        try:
            data = base64.b64decode(s, validate=True)
        except (binascii.Error, ValueError):
            return None

        mime = self._guess_mime_from_bytes(data)
        if not mime:
            return None
        return data, mime

    @staticmethod
    def _download_image(url: str) -> tuple[bytes, str] | None:
        try:
            req = Request(url, headers={"User-Agent": "generate-image-mvp/1.0"})
            with urlopen(req, timeout=20) as resp:  # nosec B310
                content_type = (resp.headers.get("Content-Type") or "").lower().split(";")[0].strip()
                data = resp.read()
            if not data:
                return None
            if content_type.startswith("image/"):
                return data, content_type

            mime = ImageGenerationService._guess_mime_from_bytes(data)
            if mime:
                return data, mime
            return None
        except Exception:
            return None

    @staticmethod
    def _guess_mime_from_bytes(data: bytes) -> str | None:
        if len(data) < 12:
            return None
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data.startswith(b"\xff\xd8"):
            return "image/jpeg"
        if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
            return "image/gif"
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "image/webp"
        return None

    def _save_generated_image(self, *, task_id: str, image_bytes: bytes, mime_type: str) -> Path:
        output_dir = Path(self.settings.data_generated_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        ext = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }.get(mime_type.lower(), ".jpg")

        output_path = output_dir / f"{task_id}_{int(time.time())}{ext}"
        output_path.write_bytes(image_bytes)
        return output_path
