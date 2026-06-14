"""Payout resource — creating and querying withdrawals.

Usage::

    from heleket import Client
    payout = Client.payout(payout_key, merchant_uuid)
    result = payout.create({"amount": "5", "currency": "USDT", ...})
"""
from __future__ import annotations

from typing import Any

from ._constants import API_VERSION
from ._request_builder import RequestBuilder

_VERSION = API_VERSION


class Payout:
    def __init__(self, payout_key: str, merchant_uuid: str) -> None:
        self._builder = RequestBuilder(payout_key, merchant_uuid)

    def create(self, data: dict[str, Any]) -> dict[str, Any] | bool:
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
        return self._builder.send_request(f"{_VERSION}/payout", data)

    def info(self, data: dict[str, Any]) -> dict[str, Any] | bool:
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
        return self._builder.send_request(f"{_VERSION}/payout/info", data)
