import re
from typing import Iterable


def is_ambiguous_question(text: str) -> bool:
    keywords = ["这个", "那个", "它", "上述", "前面", "后面"]
    return any(k in text for k in keywords) and len(text.strip()) < 20


def semantic_chunk(text: str, chunk_size: int, overlap: int) -> list[str]:
    # 轻量语义切分：按句号等断句，再拼装为近似语义块。
    chunk_size = max(1, int(chunk_size))
    overlap = max(0, int(overlap))
    sentences = [s.strip() for s in re.split(r"(?<=[。！？!?])", text) if s.strip()]
    if not sentences:
        return []

    def split_oversized_sentence(sentence: str) -> list[str]:
        sentence = str(sentence or "").strip()
        if not sentence:
            return []
        if len(sentence) <= chunk_size:
            return [sentence]
        # 兜底硬切分，避免“无标点超长句”直接突破 chunk_size。
        step = max(1, chunk_size - overlap)
        parts: list[str] = []
        start = 0
        while start < len(sentence):
            part = sentence[start : start + chunk_size].strip()
            if part:
                parts.append(part)
            start += step
        return parts

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        for sent in split_oversized_sentence(sentence):
            if len(current) + len(sent) <= chunk_size:
                current += sent
                continue

            if current:
                chunks.append(current)
            if overlap > 0 and chunks:
                tail = chunks[-1][-overlap:]
                candidate = f"{tail}{sent}"
                current = candidate if len(candidate) <= chunk_size else sent
            else:
                current = sent

    if current:
        chunks.append(current)
    return chunks


def flatten_texts(items: Iterable[dict]) -> str:
    texts: list[str] = []
    for item in items:
        text = str(item.get("text", "")).strip()
        if text:
            texts.append(text)
    return "\n".join(texts)
