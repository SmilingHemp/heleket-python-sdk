"""Payment resource — invoice creation, status, history, and webhook verification.

Usage::

    from heleket import Client
    payment = Client.payment(payment_key, merchant_uuid)
    result  = payment.create({"amount": "15", "currency": "USD", "order_id": "1"})
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from typing import Any

from ._request_builder import RequestBuilder

logger = logging.getLogger(__name__)

_VERSION = "v1"


class Payment:
    def __init__(self, payment_key: str, merchant_uuid: str) -> None:
        self._builder = RequestBuilder(payment_key, merchant_uuid)
        self._payment_key = payment_key

    def services(self, parameters: dict[str, Any] | None = None) -> dict[str, Any] | bool:
        """Get list of available payment services."""
        return self._builder.send_request(f"{_VERSION}/payment/services", parameters or {})

    def create(self, data: dict[str, Any]) -> dict[str, Any] | bool:
        """
        Create a payment invoice.

        Args:
            data: Required: amount, currency, order_id.
                  Optional: network, url_return, url_success, url_callback,
                  is_payment_multiple, lifetime, to_currency, subtract,
                  accuracy_payment_percent, additional_data, currencies,
                  except_currencies, course_source, from_referral_code,
                  discount_percent, is_refresh, payer_email.

        Returns:
            Invoice data dict with uuid, url, address, etc.

        Raises:
            ValidationError: If required fields are missing or invalid.
            AuthenticationError: If payment_key is invalid.
            APIError: For other API errors.
        """
        return self._builder.send_request(f"{_VERSION}/payment", data)

    def info(self, data: dict[str, Any] | None = None) -> dict[str, Any] | bool:
        """
        Get payment info.

        Args:
            data: Pass one of: uuid, order_id. If both passed, identified by order_id.

        Returns:
            Payment object dict.

        Raises:
            ValidationError: If neither uuid nor order_id provided.
            APIError: If payment not found.
        """
        return self._builder.send_request(f"{_VERSION}/payment/info", data or {})

    def history(self, cursor: str | None = None, parameters: dict[str, Any] | None = None) -> dict[str, Any] | bool:
        """
        Get paginated payment list.

        Args:
            cursor: Pagination cursor (nextCursor / previousCursor from previous response).
            parameters: Optional filters: date_from, date_to (format: YYYY-MM-DD H:mm:ss).

        Returns:
            Dict with items (list of payments) and paginate (cursor info).
        """
        return self._builder.send_request(
            f"{_VERSION}/payment/list", parameters or {}, cursor=cursor
        )

    def balance(self) -> dict[str, Any] | bool:
        """
        Get merchant balance (business and personal wallets).

        Returns:
            Dict with balance.merchant and balance.user arrays.
        """
        return self._builder.send_request(f"{_VERSION}/balance")

    def resend_notification(self, data: dict[str, Any]) -> dict[str, Any] | bool:
        """
        Re-send webhook notification for a finalized payment.

        Args:
            data: Pass one of: uuid, order_id.
                  Works only for finalized invoices (paid, paid_over, wrong_amount).

        Returns:
            True on success.

        Raises:
            APIError: If payment not found, no url_callback, or resend limit exceeded.
        """
        return self._builder.send_request(f"{_VERSION}/payment/resend", data)

    def create_wallet(self, data: dict[str, Any]) -> dict[str, Any] | bool:
        """
        Create a static wallet address.

        Args:
            data: Required: currency, network, order_id.
                  Optional: url_callback, from_referral_code.

        Returns:
            Dict with wallet_uuid, uuid, address, network, currency, url.
        """
        return self._builder.send_request(f"{_VERSION}/wallet", data)

    def verify_webhook(self, payload: bytes | str, sign: str) -> bool:
        """
        Verify incoming webhook signature.

        Per API docs: extract sign from body, remove it, re-encode remaining
        data and compare: md5(base64_encode(json_body) + payment_key).

        Args:
            payload: Raw request body (bytes or str).
            sign: The sign value extracted from the webhook body.

        Returns:
            True if signature is valid, False otherwise.
        """
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")

        try:
            data: dict[str, Any] = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("verify_webhook: failed to parse payload as JSON")
            return False

        data.pop("sign", None)

        # PHP json_encode escapes slashes — must match exactly
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("/", "\\/")
        encoded = base64.b64encode(body.encode("utf-8")).decode("utf-8")
        expected = hashlib.md5((encoded + self._payment_key).encode("utf-8")).hexdigest()

        return hmac.compare_digest(expected, sign)
