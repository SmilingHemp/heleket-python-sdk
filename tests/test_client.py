from __future__ import annotations

import pytest

from heleket import Client, Payment, Payout
from tests.conftest import MERCHANT_UUID, PAYMENT_KEY, PAYOUT_KEY


@pytest.mark.unit
class TestClient:
    def test_payment_returns_payment_instance(self):
        p = Client.payment(PAYMENT_KEY, MERCHANT_UUID)
        assert isinstance(p, Payment)

    def test_payout_returns_payout_instance(self):
        po = Client.payout(PAYOUT_KEY, MERCHANT_UUID)
        assert isinstance(po, Payout)

    def test_payment_raises_on_empty_key(self):
        with pytest.raises(ValueError):
            Client.payment("", MERCHANT_UUID)

    def test_payout_raises_on_empty_key(self):
        with pytest.raises(ValueError):
            Client.payout("", MERCHANT_UUID)
