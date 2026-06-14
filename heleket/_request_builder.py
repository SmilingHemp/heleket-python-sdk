"""Internal HTTP transport layer for the Heleket SDK.

Not part of the public API — import from heleket directly:

    from heleket import Client, Payment, Payout

RequestBuilder handles request signing, serialisation, and error mapping.
It is injectable via the ``opener`` constructor argument for unit testing
without any network calls or external mocking libraries.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import urllib.error
import urllib.request
from typing import Any

from .exceptions import APIError, AuthenticationError, ConnectionError, ValidationError

logger = logging.getLogger(__name__)

API_URL = "https://api.heleket.com/"


class RequestBuilder:
    def __init__(
        self,
        secret_key: str,
        merchant_uuid: str,
        opener: urllib.request.OpenerDirector | None = None,
    ) -> None:
        if not secret_key:
            raise ValueError("secret_key cannot be empty")
        if not merchant_uuid:
            raise ValueError("merchant_uuid cannot be empty")
        self._secret_key = secret_key
        self._merchant_uuid = merchant_uuid
        self._opener = opener or urllib.request.build_opener()

    def _build_sign(self, body: str) -> str:
        # Per API docs: sign = md5(base64_encode(body) + API_KEY)
        encoded = base64.b64encode(body.encode("utf-8")).decode("utf-8")
        return hashlib.md5((encoded + self._secret_key).encode("utf-8")).hexdigest()

    def send_request(
        self, uri: str, data: dict[str, Any] | None = None, cursor: str | None = None
    ) -> dict[str, Any] | bool:
        """
        Send a signed POST request to the API.

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

        url = API_URL + uri
        if cursor is not None:
            url = f"{url}?cursor={cursor}"

        body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        body_bytes = body.encode("utf-8")
        sign = self._build_sign(body)

        logger.debug("POST %s body_len=%d", uri, len(body))

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json;charset=UTF-8",
            "merchant": self._merchant_uuid,
            "sign": sign,
        }

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")

        try:
            with self._opener.open(req) as resp:
                response_code: int = resp.getcode()
                raw: str = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            response_code = e.code
            raw = e.read().decode("utf-8")
        except urllib.error.URLError as e:
            raise ConnectionError(str(e.reason)) from e

        if not raw:
            return True

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as e:
            raise APIError(str(e), response_code, uri) from e

        if response_code == 401:
            raise AuthenticationError(result.get("message", "Invalid API key"))

        state = result.get("state")

        if response_code != 200 or (state is not None and state != 0):
            message = result.get("message")
            errors = result.get("errors")
            if errors:
                raise ValidationError("Validation error", uri, errors)
            raise APIError(message or "Unknown API error", response_code, uri)

        if state == 0:
            api_result = result.get("result")
            if api_result is not None and api_result != [] and api_result != {}:
                return api_result
            return True

        return True
