from __future__ import annotations

import asyncio
import logging

from app.clients.embedding_client import EmbeddingClient

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(
        self,
        client: EmbeddingClient,
        batch_size: int = 64,
        max_retries: int = 3,
        retry_backoff_sec: float = 2.0,
    ):
        self.client = client
        self.batch_size = max(1, batch_size)
        self.max_retries = max(1, max_retries)
        self.retry_backoff_sec = max(0.1, retry_backoff_sec)

    async def embed_texts(self, texts: list[str]) -> list[dict]:
        if not texts:
            return []
        result: list[dict] = []
        total = len(texts)

        for start in range(0, total, self.batch_size):
            end = min(start + self.batch_size, total)
            batch = texts[start:end]
            last_exc: Exception | None = None

            for attempt in range(1, self.max_retries + 1):
                try:
                    logger.info(
                        "embedding batch request start=%s end=%s size=%s attempt=%s/%s",
                        start,
                        end,
                        len(batch),
                        attempt,
                        self.max_retries,
                    )
                    data = await self.client.embed(batch)
                    if len(data) != len(batch):
                        raise RuntimeError(
                            f"embedding response size mismatch: got={len(data)} expected={len(batch)} batch={start}:{end}"
                        )
                    result.extend(data)
                    last_exc = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if attempt >= self.max_retries:
                        break
                    wait_sec = self.retry_backoff_sec * attempt
                    logger.warning(
                        "embedding batch failed start=%s end=%s attempt=%s/%s err=%s retry_in=%.1fs",
                        start,
                        end,
                        attempt,
                        self.max_retries,
                        exc,
                        wait_sec,
                    )
                    await asyncio.sleep(wait_sec)

            if last_exc is not None:
                raise RuntimeError(
                    f"embedding failed after retries: batch={start}:{end} size={len(batch)} err={last_exc}"
                ) from last_exc

        return result
