from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx


class LlmClient:
    def __init__(self, url: str, api_key: str, model_name: str, max_tokens: int):
        self.url = url
        self.api_key = api_key
        self.model_name = model_name
        self.max_tokens = max_tokens

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            if self.api_key.startswith(("Bearer ", "Basic ")):
                headers["Authorization"] = self.api_key
            else:
                headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _stream_token_candidates(self) -> list[int | None]:
        # 先走 provider 默认策略（不传 max_tokens），避免部分模型因超大上限直接 400。
        # 若失败再回退到用户配置和保守档位。
        preferred = max(1, int(self.max_tokens))
        candidates: list[int | None] = [None, preferred]
        for n in (8192, 4096, 2048, 1024):
            if n not in candidates:
                candidates.append(n)
        return candidates

    async def _stream_chat_once(self, messages: list[dict], max_tokens: int | None) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
        }
        if isinstance(max_tokens, int) and max_tokens > 0:
            payload["max_tokens"] = max_tokens
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", self.url, headers=self._headers(), json=payload) as resp:
                if resp.status_code >= 400:
                    body = (await resp.aread()).decode("utf-8", errors="ignore")[:1000]
                    raise RuntimeError(
                        f"llm stream failed status={resp.status_code} model={self.model_name} max_tokens={max_tokens} body={body}"
                    )
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.strip() == "data: [DONE]":
                        break
                    if not line.startswith("data:"):
                        continue
                    yield line

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        last_error: Exception | None = None
        candidates = self._stream_token_candidates()
        for idx, max_tokens in enumerate(candidates):
            try:
                async for line in self._stream_chat_once(messages, max_tokens=max_tokens):
                    yield line
                return
            except RuntimeError as exc:
                last_error = exc
                # 只有 400 才回退 token 档位，其它错误直接抛出。
                if "status=400" not in str(exc) or idx == len(candidates) - 1:
                    raise
                continue
        if last_error:
            raise last_error

    async def complete(self, messages: list[dict]) -> str:
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "max_tokens": 256,
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(self.url, headers=self._headers(), json=payload)
            if resp.status_code >= 400:
                body = resp.text[:1000] if resp.text else ""
                raise RuntimeError(
                    f"llm complete failed status={resp.status_code} model={self.model_name} body={body}"
                )
            body = resp.json()
            choices = body.get("choices", [])
            if not choices:
                return ""
            message = choices[0].get("message", {})
            return str(message.get("content", "")).strip()
