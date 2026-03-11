from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any


def image_to_data_url(image_path: str) -> str:
    p = Path(image_path)
    if not p.exists() or not p.is_file():
        raise RuntimeError(f"image file not found: {image_path}")
    mime_type = mimetypes.guess_type(str(p))[0] or "image/jpeg"
    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"


def image_embedding_payload_candidates(image_paths: list[str]) -> list[list[Any]]:
    # Different OpenAI-compatible providers accept slightly different embedding input schemas.
    data_urls = [image_to_data_url(p) for p in image_paths]
    return [
        [{"image": u} for u in data_urls],
        [{"type": "image_url", "image_url": {"url": u}} for u in data_urls],
        [{"type": "input_image", "image_url": u} for u in data_urls],
        data_urls,
    ]
