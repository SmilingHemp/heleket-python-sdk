from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

MERCHANT_UUID = "test-merchant-uuid"
PAYMENT_KEY = "test-payment-key"
PAYOUT_KEY = "test-payout-key"


def make_response(data: dict, status: int = 200) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.getcode.return_value = status
    mock_resp.read.return_value = json.dumps(data).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def make_error_response(data: dict, status: int) -> MagicMock:
    import urllib.error

    mock_err = urllib.error.HTTPError(
        url="", code=status, msg="", hdrs=None, fp=None  # type: ignore[arg-type]
    )
    mock_err.read = MagicMock(return_value=json.dumps(data).encode("utf-8"))
    mock_err.code = status
    return mock_err


@pytest.fixture
def mock_opener() -> MagicMock:
    return MagicMock()


@pytest.fixture
def payment_client(mock_opener: MagicMock):
    from heleket import Payment
    from heleket._request_builder import RequestBuilder

    p = Payment.__new__(Payment)
    p._payment_key = PAYMENT_KEY
    p._builder = RequestBuilder(PAYMENT_KEY, MERCHANT_UUID, opener=mock_opener)
    return p


@pytest.fixture
def payout_client(mock_opener: MagicMock):
    from heleket import Payout
    from heleket._request_builder import RequestBuilder

    po = Payout.__new__(Payout)
    po._builder = RequestBuilder(PAYOUT_KEY, MERCHANT_UUID, opener=mock_opener)
    return po
