from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class LayoutClient:
    def __init__(
        self,
        url: str,
        token: str,
        fallback_url: str = "",
        file_type: int = 0,
        max_num_imgs: int = 512,
        timeout_sec: int = 300,
    ):
        self.url = url
        self.token = token
        self.fallback_url = fallback_url
        self.file_type = file_type
        self.max_num_imgs = max_num_imgs
        self.timeout_sec = timeout_sec

    def _headers(self, json_mode: bool = True) -> dict[str, str]:
        headers: dict[str, str] = {}
        if json_mode:
            headers["Content-Type"] = "application/json"
        if self.token:
            if self.token.startswith("Bearer "):
                headers["Authorization"] = self.token
            else:
                headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @staticmethod
    def _raise_with_body(resp: httpx.Response, mode: str) -> None:
        body = resp.text[:1000] if resp.text else ""
        raise RuntimeError(f"layout parse failed ({mode}) status={resp.status_code} body={body}")

    @staticmethod
    def _raise_if_business_error(payload: dict[str, Any], mode: str) -> None:
        # 某些服务即使业务失败也会返回 HTTP 200，这里统一兜底。
        if not isinstance(payload, dict):
            return
        error_code = payload.get("errorCode")
        if error_code is None:
            return
        if str(error_code) in {"0", "200"}:
            return
        log_id = payload.get("logId", "")
        error_msg = payload.get("errorMsg", "")
        raise RuntimeError(f"layout parse business error ({mode}) errorCode={error_code} logId={log_id} errorMsg={error_msg}")

    async def _parse_by_url(self, target_url: str, file_url: str) -> dict[str, Any]:
        page_limit = self.max_num_imgs
        payload = {
            "file": file_url,
            "fileType": self.file_type,
            "max_num_imgs": self.max_num_imgs,
            "maxNumImgs": self.max_num_imgs,
            "max_num_pages": page_limit,
            "maxNumPages": page_limit,
            "page_limit": page_limit,
            "parse_all_pages": True,
            "use_chart_recognition": True,
            "format_block_content": True,
            "options": {
                "max_num_imgs": self.max_num_imgs,
                "max_num_pages": page_limit,
                "parse_all_pages": True,
                "use_chart_recognition": True,
                "format_block_content": True,
                "merge_layout_blocks": True,
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            resp = await client.post(target_url, headers=self._headers(json_mode=True), json=payload)
            if resp.status_code >= 400:
                self._raise_with_body(resp, mode=f"url:{target_url}")
            body = resp.json()
            self._raise_if_business_error(body, mode=f"url:{target_url}")
            return body

    async def parse(self, file_url: str) -> dict[str, Any]:
        try:
            return await self._parse_by_url(self.url, file_url)
        except Exception as exc:  # noqa: BLE001
            if not self.fallback_url or self.fallback_url == self.url:
                raise
            logger.warning(
                "layout parse primary failed primary=%s err=%s; fallback=%s",
                self.url,
                exc,
                self.fallback_url,
            )
            return await self._parse_by_url(self.fallback_url, file_url)

    async def parse_upload(self, filename: str, content: bytes) -> dict[str, Any]:
        files = {"file": (filename, content, "application/pdf")}
        data = {
            "fileType": str(self.file_type),
            "max_num_imgs": str(self.max_num_imgs),
            "maxNumImgs": str(self.max_num_imgs),
            "max_num_pages": str(self.max_num_imgs),
            "maxNumPages": str(self.max_num_imgs),
            "page_limit": str(self.max_num_imgs),
            "parse_all_pages": "true",
            "use_chart_recognition": "true",
            "format_block_content": "true",
        }
        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            resp = await client.post(self.url, headers=self._headers(json_mode=False), data=data, files=files)
            if resp.status_code >= 400:
                self._raise_with_body(resp, mode="upload")
            body = resp.json()
            self._raise_if_business_error(body, mode="upload")
            return body
