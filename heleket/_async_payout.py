"""Async Payout resource — creating and querying withdrawals.

Usage::

    from heleket import AsyncClient

    async with AsyncClient.payout(payout_key, merchant_uuid) as payout:
        result = await payout.create({"amount": "5", "currency": "USDT", ...})
"""
from __future__ import annotations

from typing import Any

import httpx

from ._async_request_builder import AsyncRequestBuilder
from ._constants import API_VERSION

_VERSION = API_VERSION


class AsyncPayout:
    def __init__(
        self,
        payout_key: str,
        merchant_uuid: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._builder = AsyncRequestBuilder(payout_key, merchant_uuid, http_client)

    async def __aenter__(self) -> AsyncPayout:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._builder.close()

    async def create(self, data: dict[str, Any]) -> dict[str, Any] | bool:
        """
        Create a payout.

        Args:
            data: Required: amount, currency, network, order_id, address, is_subtract.
                  Optional: url_callback, to_currency, course_source,
                  from_currency, priority, memo.

        Returns:
            Payout data dict.

        Raises:
            ValidationError: If required fields are missing or invalid.
            AuthenticationError: If payout_key is invalid.
            APIError: For other API errors.
        """
        return await self._builder.send_request(f"{_VERSION}/payout", data)

    async def info(self, data: dict[str, Any]) -> dict[str, Any] | bool:
        """
        Get payout info.

        Args:
            data: Pass one of: uuid, order_id. If both passed, identified by order_id.

        Returns:
            Payout object dict.

        Raises:
            ValidationError: If neither uuid nor order_id provided.
            APIError: If payout not found.
        """
        return await self._builder.send_request(f"{_VERSION}/payout/info", data)
