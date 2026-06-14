"""Entry point for the Heleket SDK.

Sync usage::

    from heleket import Client
    payment = Client.payment(payment_key, merchant_uuid)
    payout  = Client.payout(payout_key, merchant_uuid)

Async usage::

    from heleket import AsyncClient

    async with AsyncClient.payment(payment_key, merchant_uuid) as payment:
        result = await payment.create({...})
"""
from __future__ import annotations

from typing import Any

from ._async_payment import AsyncPayment
from ._async_payout import AsyncPayout
from .payment import Payment
from .payout import Payout


class Client:
    @staticmethod
    def payment(payment_key: str, merchant_uuid: str) -> Payment:
        """Create a sync Payment resource instance."""
        return Payment(payment_key, merchant_uuid)

    @staticmethod
    def payout(payout_key: str, merchant_uuid: str) -> Payout:
        """Create a sync Payout resource instance."""
        return Payout(payout_key, merchant_uuid)


class AsyncClient:
    @staticmethod
    def payment(payment_key: str, merchant_uuid: str) -> AsyncPayment:
        """Create an async Payment resource instance."""
        return AsyncPayment(payment_key, merchant_uuid)

    @staticmethod
    def payout(payout_key: str, merchant_uuid: str) -> AsyncPayout:
        """Create an async Payout resource instance."""
        return AsyncPayout(payout_key, merchant_uuid)
