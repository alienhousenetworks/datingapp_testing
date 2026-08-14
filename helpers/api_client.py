"""Thin HTTP client for integration and load-prep scripts."""
from __future__ import annotations

from typing import Any, Optional

import requests

from suite_config.test_settings import test_config


class APIClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        access_token: Optional[str] = None,
        device_id: Optional[str] = None,
    ):
        self.base_url = (base_url or test_config.base_url).rstrip("/")
        self.timeout = timeout if timeout is not None else test_config.http_timeout
        self.access_token = access_token
        self.device_id = device_id
        self.session = requests.Session()

    @property
    def api_v1(self) -> str:
        return f"{self.base_url}/api/v1"

    def _headers(self, extra: Optional[dict] = None) -> dict:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if self.device_id:
            headers["X-Device-ID"] = self.device_id
        if extra:
            headers.update(extra)
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        auth: bool = True,
        absolute: bool = False,
    ) -> requests.Response:
        url = path if absolute or path.startswith("http") else f"{self.base_url}{path}"
        use_headers = self._headers(headers)
        if not auth:
            use_headers.pop("Authorization", None)
        return self.session.request(
            method=method.upper(),
            url=url,
            json=json,
            params=params,
            headers=use_headers,
            timeout=self.timeout,
        )

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs) -> requests.Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        return self.request("DELETE", path, **kwargs)

    def set_token(self, access_token: str) -> None:
        self.access_token = access_token
