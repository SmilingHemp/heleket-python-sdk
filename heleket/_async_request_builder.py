"""Internal async HTTP transport layer for the Heleket SDK.

Not part of the public API — import from heleket directly:

    from heleket import AsyncClient

AsyncRequestBuilder uses httpx.AsyncClient and mirrors the sync
RequestBuilder interface. Inject ``http_client`` for testing::

    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={...}))
    builder = AsyncRequestBuilder(key, uuid, http_client=httpx.AsyncClient(transport=transport))
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Any

import httpx

from ._constants import API_URL, API_VERSION, DEFAULT_TIMEOUT
from .exceptions import APIError, AuthenticationError, ConnectionError, ValidationError

logger = logging.getLogger(__name__)


class AsyncRequestBuilder:
    def __init__(
        self,
        secret_key: str,
        merchant_uuid: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not secret_key:
            raise ValueError("secret_key cannot be empty")
        if not merchant_uuid:
            raise ValueError("merchant_uuid cannot be empty")
        self._secret_key = secret_key
        self._merchant_uuid = merchant_uuid
        self._http_client = http_client
        self._owned = http_client is None  # True — we created it, we close it

    def _build_sign(self, body: str) -> str:
        encoded = base64.b64encode(body.encode("utf-8")).decode("utf-8")
        return hashlib.md5((encoded + self._secret_key).encode("utf-8")).hexdigest()

    def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(base_url=API_URL, timeout=DEFAULT_TIMEOUT)
        return self._http_client

    async def close(self) -> None:
        """Close the underlying HTTP client if it was created internally."""
        if self._owned and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    def _parse_response(
        self, status_code: int, raw: str, uri: str
    ) -> dict[str, Any] | bool:
        if not raw:
            return True

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as e:
            raise APIError(str(e), status_code, uri) from e

        if status_code == 401:
            raise AuthenticationError(result.get("message", "Invalid API key"))

        state = result.get("state")

        if status_code != 200 or (state is not None and state != 0):
            errors = result.get("errors")
            message = result.get("message")
            if errors:
                raise ValidationError("Validation error", uri, errors)
            raise APIError(message or "Unknown API error", status_code, uri)

        if state == 0:
            api_result = result.get("result")
            if api_result is not None and api_result != [] and api_result != {}:
                return api_result
            return True

        return True

    async def send_request(
        self, uri: str, data: dict[str, Any] | None = None, cursor: str | None = None
    ) -> dict[str, Any] | bool:
        """
        Send a signed async POST request to the API.

        Args:
            uri: API endpoint path (e.g. 'v1/payment').
            data: Request body as dict.
            cursor: Pagination cursor, appended as ?cursor= query param.

        Returns:
            result dict from API response, or True if result is empty.

        Raises:
            AuthenticationError: On 401.
            ValidationError: On 422 with field errors.
            APIError: On other API errors.
            ConnectionError: On network/timeout errors.
        """
        if data is None:
            data = {}

        url = uri if cursor is None else f"{uri}?cursor={cursor}"
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        sign = self._build_sign(body)

        logger.debug("POST %s body_len=%d", uri, len(body))

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json;charset=UTF-8",
            "merchant": self._merchant_uuid,
            "sign": sign,
        }

        try:
            resp = await self._get_client().post(
                url, content=body.encode("utf-8"), headers=headers
            )
        except httpx.TimeoutException as e:
            raise ConnectionError(str(e)) from e
        except httpx.RequestError as e:
            raise ConnectionError(str(e)) from e

        return self._parse_response(resp.status_code, resp.text, uri)
