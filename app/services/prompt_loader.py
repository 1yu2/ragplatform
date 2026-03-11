from __future__ import annotations

from functools import lru_cache
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
PROMPTS_DIR = ROOT_DIR / "prompts"


@lru_cache(maxsize=64)
def load_prompt(prompt_file: str, fallback: str) -> str:
    path = PROMPTS_DIR / prompt_file
    try:
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    except Exception:
        pass
    return fallback
