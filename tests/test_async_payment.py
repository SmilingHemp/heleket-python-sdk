from __future__ import annotations

import base64
import hashlib
import json

import httpx
import pytest

from heleket._async_payment import AsyncPayment
from heleket.exceptions import APIError, AuthenticationError, ConnectionError, ValidationError
from tests.conftest import MERCHANT_UUID, PAYMENT_KEY


def make_client(data: dict, status: int = 200) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(status, json=data)),
        base_url="https://api.heleket.com/",
    )


def make_payment(data: dict, status: int = 200) -> AsyncPayment:
    return AsyncPayment(PAYMENT_KEY, MERCHANT_UUID, http_client=make_client(data, status))


@pytest.mark.unit
class TestAsyncPaymentCreate:
    async def test_create_success(self):
        result_data = {"uuid": "abc-123", "url": "https://pay.heleket.com/pay/abc-123", "status": "check"}
        async with make_payment({"state": 0, "result": result_data}) as payment:
            result = await payment.create({"amount": "15", "currency": "USD", "order_id": "1"})

        assert result["uuid"] == "abc-123"

    async def test_create_validation_error(self):
        async with make_payment({"state": 1, "errors": {"amount": ["validation.required"]}}, 422) as payment:
            with pytest.raises(ValidationError) as exc_info:
                await payment.create({"currency": "USD", "order_id": "1"})

        assert "amount" in exc_info.value.errors

    async def test_create_auth_error(self):
        async with make_payment({"message": "Unauthenticated."}, 401) as payment:
            with pytest.raises(AuthenticationError):
                await payment.create({"amount": "15", "currency": "USD", "order_id": "1"})

    async def test_create_connection_error(self):
        def handler(r: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("timeout")

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.heleket.com/"
        )
        async with AsyncPayment(PAYMENT_KEY, MERCHANT_UUID, http_client=client) as payment:
            with pytest.raises(ConnectionError):
                await payment.create({"amount": "15", "currency": "USD", "order_id": "1"})

    async def test_create_api_error(self):
        async with make_payment({"state": 1, "message": "The currency was not found"}) as payment:
            with pytest.raises(APIError) as exc_info:
                await payment.create({"amount": "15", "currency": "INVALID", "order_id": "1"})

        assert "currency was not found" in str(exc_info.value)


@pytest.mark.unit
class TestAsyncPaymentInfo:
    async def test_info_by_uuid(self):
        result_data = {"uuid": "70b8db5c", "status": "cancel"}
        async with make_payment({"state": 0, "result": result_data}) as payment:
            result = await payment.info({"uuid": "70b8db5c"})

        assert result["uuid"] == "70b8db5c"

    async def test_info_validation_error(self):
        async with make_payment(
            {"state": 1, "errors": {"uuid": ["validation.required_without"], "order_id": ["validation.required_without"]}},
            422,
        ) as payment:
            with pytest.raises(ValidationError):
                await payment.info({})


@pytest.mark.unit
class TestAsyncPaymentHistory:
    async def test_history_success(self):
        paginate = {"count": 0, "hasPages": False, "nextCursor": None, "previousCursor": None, "perPage": 15}
        async with make_payment({"state": 0, "result": {"items": [], "paginate": paginate}}) as payment:
            result = await payment.history()

        assert "items" in result
        assert "paginate" in result

    async def test_history_cursor_passed(self):
        captured: list[httpx.Request] = []

        def handler(r: httpx.Request) -> httpx.Response:
            captured.append(r)
            return httpx.Response(200, json={"state": 0, "result": {"items": [], "paginate": {}}})

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.heleket.com/"
        )
        async with AsyncPayment(PAYMENT_KEY, MERCHANT_UUID, http_client=client) as payment:
            await payment.history(cursor="eyJpZCI6MjEyfQ")

        assert "cursor=eyJpZCI6MjEyfQ" in str(captured[0].url)


@pytest.mark.unit
class TestAsyncPaymentBalance:
    async def test_balance_success(self):
        result_data = [{"balance": {"merchant": [], "user": []}}]
        async with make_payment({"state": 0, "result": result_data}) as payment:
            result = await payment.balance()

        assert isinstance(result, list)


@pytest.mark.unit
class TestAsyncPaymentResend:
    async def test_resend_success(self):
        async with make_payment({"state": 0, "result": []}) as payment:
            result = await payment.resend_notification({"order_id": "ord_1"})

        assert result is True

    async def test_resend_not_found(self):
        async with make_payment({"state": 1, "message": "Payment not found"}) as payment:
            with pytest.raises(APIError):
                await payment.resend_notification({"order_id": "nonexistent"})


@pytest.mark.unit
class TestAsyncPaymentCreateWallet:
    async def test_create_wallet_success(self):
        result_data = {
            "wallet_uuid": "de15b0f6",
            "uuid": "87961ae5",
            "order_id": "wallet_1",
            "address": "TExampleAddr1000000000000000000000",
            "network": "tron",
            "currency": "USDT",
            "url": "https://pay.heleket.com/wallet/abc",
        }
        async with make_payment({"state": 0, "result": result_data}) as payment:
            result = await payment.create_wallet({
                "currency": "USDT", "network": "tron", "order_id": "wallet_1",
            })

        assert result["address"] == "TExampleAddr1000000000000000000000"


@pytest.mark.unit
class TestAsyncPaymentServices:
    async def test_services_success(self):
        async with make_payment({"state": 0, "result": [{"network": "tron", "currency": "USDT"}]}) as payment:
            result = await payment.services()

        assert isinstance(result, list)


@pytest.mark.unit
class TestAsyncVerifyWebhook:
    """verify_webhook is sync — identical algorithm to sync Payment."""

    def _make_payload(self, data: dict) -> tuple[str, str]:
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("/", "\\/")
        encoded = base64.b64encode(body.encode()).decode()
        sign = hashlib.md5((encoded + PAYMENT_KEY).encode()).hexdigest()
        payload_data = dict(data)
        payload_data["sign"] = sign
        return json.dumps(payload_data, ensure_ascii=False, separators=(",", ":")), sign

    def _payment(self) -> AsyncPayment:
        return AsyncPayment(PAYMENT_KEY, MERCHANT_UUID)

    def test_valid_signature(self):
        data = {"type": "payment", "uuid": "abc", "status": "paid", "order_id": "1"}
        payload, sign = self._make_payload(data)
        assert self._payment().verify_webhook(payload, sign) is True

    def test_valid_bytes_payload(self):
        data = {"type": "payment", "uuid": "abc", "status": "paid", "order_id": "1"}
        payload, sign = self._make_payload(data)
        assert self._payment().verify_webhook(payload.encode(), sign) is True

    def test_slash_in_txid(self):
        data = {"uuid": "abc", "txid": "someTxidWith/Slash", "status": "paid", "order_id": "1"}
        payload, sign = self._make_payload(data)
        assert self._payment().verify_webhook(payload, sign) is True

    def test_invalid_signature(self):
        data = {"uuid": "abc", "status": "paid", "order_id": "1"}
        payload, _ = self._make_payload(data)
        assert self._payment().verify_webhook(payload, "invalidsign00000000000000000000") is False

    def test_tampered_payload(self):
        data = {"uuid": "abc", "amount": "10.00", "status": "paid", "order_id": "1"}
        payload, sign = self._make_payload(data)
        tampered = payload.replace('"amount":"10.00"', '"amount":"999.00"')
        assert self._payment().verify_webhook(tampered, sign) is False

    def test_invalid_json(self):
        assert self._payment().verify_webhook("not-json", "anysign") is False


@pytest.mark.unit
class TestAsyncPaymentContextManager:
    async def test_context_manager(self):
        client = make_client({"state": 0, "result": {"uuid": "abc"}})
        async with AsyncPayment(PAYMENT_KEY, MERCHANT_UUID, http_client=client) as payment:
            assert payment is not None
        # after exit — client closed, no error
