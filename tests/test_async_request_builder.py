from __future__ import annotations

import base64
import hashlib
import json

import httpx
import pytest

from heleket._async_request_builder import AsyncRequestBuilder
from heleket.exceptions import APIError, AuthenticationError, ConnectionError, ValidationError
from tests.conftest import MERCHANT_UUID, PAYMENT_KEY


def make_transport(data: dict, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=data)
    return httpx.MockTransport(handler)


def make_client(data: dict, status: int = 200) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=make_transport(data, status), base_url="https://api.heleket.com/"
    )


@pytest.mark.unit
class TestAsyncRequestBuilderInit:
    def test_raises_on_empty_key(self):
        with pytest.raises(ValueError):
            AsyncRequestBuilder("", MERCHANT_UUID)

    def test_raises_on_empty_uuid(self):
        with pytest.raises(ValueError):
            AsyncRequestBuilder(PAYMENT_KEY, "")


@pytest.mark.unit
class TestAsyncBuildSign:
    def test_sign_matches_sync(self):
        builder = AsyncRequestBuilder(PAYMENT_KEY, MERCHANT_UUID)
        body = '{"amount":"10","currency":"USDT"}'
        encoded = base64.b64encode(body.encode()).decode()
        expected = hashlib.md5((encoded + PAYMENT_KEY).encode()).hexdigest()
        assert builder._build_sign(body) == expected


@pytest.mark.unit
class TestAsyncSendRequest:
    async def test_success_returns_result(self):
        result_data = {"uuid": "abc-123", "url": "https://pay.heleket.com/pay/abc-123"}
        client = make_client({"state": 0, "result": result_data})

        builder = AsyncRequestBuilder(PAYMENT_KEY, MERCHANT_UUID, http_client=client)
        result = await builder.send_request("v1/payment", {"amount": "10", "currency": "USDT", "order_id": "1"})

        assert result == result_data
        await client.aclose()

    async def test_returns_true_when_result_empty(self):
        client = make_client({"state": 0, "result": []})
        builder = AsyncRequestBuilder(PAYMENT_KEY, MERCHANT_UUID, http_client=client)

        result = await builder.send_request("v1/payment/resend", {"order_id": "1"})

        assert result is True
        await client.aclose()

    async def test_cursor_appended_to_url(self):
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={"state": 0, "result": {"items": [], "paginate": {}}})

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.heleket.com/"
        )
        builder = AsyncRequestBuilder(PAYMENT_KEY, MERCHANT_UUID, http_client=client)
        await builder.send_request("v1/payment/list", {}, cursor="eyJpZCI6MjEyfQ")

        assert "cursor=eyJpZCI6MjEyfQ" in str(captured[0].url)
        await client.aclose()

    async def test_raises_validation_error_on_422(self):
        client = make_client(
            {"state": 1, "errors": {"amount": ["validation.required"]}}, status=422
        )
        builder = AsyncRequestBuilder(PAYMENT_KEY, MERCHANT_UUID, http_client=client)

        with pytest.raises(ValidationError) as exc_info:
            await builder.send_request("v1/payment", {})

        assert exc_info.value.errors == {"amount": ["validation.required"]}
        await client.aclose()

    async def test_raises_api_error_on_state_1(self):
        client = make_client({"state": 1, "message": "The currency was not found"})
        builder = AsyncRequestBuilder(PAYMENT_KEY, MERCHANT_UUID, http_client=client)

        with pytest.raises(APIError) as exc_info:
            await builder.send_request("v1/payment", {})

        assert "currency was not found" in str(exc_info.value)
        await client.aclose()

    async def test_raises_authentication_error_on_401(self):
        client = make_client({"message": "Unauthenticated."}, status=401)
        builder = AsyncRequestBuilder(PAYMENT_KEY, MERCHANT_UUID, http_client=client)

        with pytest.raises(AuthenticationError):
            await builder.send_request("v1/payment", {})

        await client.aclose()

    async def test_raises_connection_error_on_network_failure(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.heleket.com/"
        )
        builder = AsyncRequestBuilder(PAYMENT_KEY, MERCHANT_UUID, http_client=client)

        with pytest.raises(ConnectionError):
            await builder.send_request("v1/payment", {})

        await client.aclose()

    async def test_sign_and_merchant_headers(self):
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={"state": 0, "result": {}})

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.heleket.com/"
        )
        builder = AsyncRequestBuilder(PAYMENT_KEY, MERCHANT_UUID, http_client=client)
        data = {"amount": "10"}
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        expected_sign = builder._build_sign(body)

        await builder.send_request("v1/payment", data)

        req = captured[0]
        assert req.headers["sign"] == expected_sign
        assert req.headers["merchant"] == MERCHANT_UUID
        await client.aclose()

    async def test_context_manager_closes_client(self):
        client = make_client({"state": 0, "result": {"uuid": "abc"}})
        builder = AsyncRequestBuilder(PAYMENT_KEY, MERCHANT_UUID, http_client=client)
        builder._owned = True  # simulate owned client

        await builder.close()
        assert builder._http_client is None
