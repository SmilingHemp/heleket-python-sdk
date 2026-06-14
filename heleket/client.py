"""Entry point for the Heleket SDK.

Usage::

    from heleket import Client
    payment = Client.payment(payment_key, merchant_uuid)
    payout  = Client.payout(payout_key, merchant_uuid)
"""
from __future__ import annotations

from typing import Any

from .payment import Payment
from .payout import Payout


class Client:
    @staticmethod
    def payment(payment_key: str, merchant_uuid: str) -> Payment:
        """Create a Payment resource instance."""
        return Payment(payment_key, merchant_uuid)

    @staticmethod
    def payout(payout_key: str, merchant_uuid: str) -> Payout:
        """Create a Payout resource instance."""
        return Payout(payout_key, merchant_uuid)
