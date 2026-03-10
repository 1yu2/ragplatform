from __future__ import annotations

from typing import Any

import httpx


class EmbeddingClient:
    def __init__(
        self,
        url: str,
        model_name: str,
        api_key: str = "",
        auth_header: str = "Authorization",
        auth_scheme: str = "Bearer",
        timeout_sec: int = 300,
    ):
        self.url = url
        self.model_name = model_name
        self.api_key = api_key
        self.auth_header = auth_header
        self.auth_scheme = auth_scheme
        self.timeout_sec = timeout_sec

    async def embed(self, texts: list[str]) -> list[dict[str, Any]]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            if self.auth_header.lower() == "authorization":
                if self.api_key.startswith(("Bearer ", "Basic ")):
                    headers[self.auth_header] = self.api_key
                elif self.auth_scheme:
                    headers[self.auth_header] = f"{self.auth_scheme} {self.api_key}"
                else:
                    headers[self.auth_header] = self.api_key
            else:
                headers[self.auth_header] = self.api_key

        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            resp = await client.post(self.url, headers=headers, json={"model": self.model_name, "input": texts})
            resp.raise_for_status()
            data = resp.json().get("data", [])
            if not isinstance(data, list):
                return []
            return data
