from __future__ import annotations

import httpx
import pytest

from heleket._async_payout import AsyncPayout
from heleket.exceptions import APIError, AuthenticationError, ConnectionError, ValidationError
from tests.conftest import MERCHANT_UUID, PAYOUT_KEY


def make_payout(data: dict, status: int = 200) -> AsyncPayout:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(status, json=data)),
        base_url="https://api.heleket.com/",
    )
    return AsyncPayout(PAYOUT_KEY, MERCHANT_UUID, http_client=client)


@pytest.mark.unit
class TestAsyncPayoutCreate:
    async def test_create_success(self):
        result_data = {
            "uuid": "a7c0caec",
            "amount": "5",
            "currency": "USDT",
            "network": "TRON",
            "status": "process",
        }
        async with make_payout({"state": 0, "result": result_data}) as payout:
            result = await payout.create({
                "amount": "5", "currency": "USDT", "network": "TRON",
                "order_id": "payout_1", "address": "TExampleAddr2", "is_subtract": True,
            })

        assert result["uuid"] == "a7c0caec"
        assert result["status"] == "process"

    async def test_create_validation_error(self):
        async with make_payout({"state": 1, "errors": {"address": ["validation.required"]}}, 422) as payout:
            with pytest.raises(ValidationError) as exc_info:
                await payout.create({"amount": "5", "currency": "USDT", "network": "TRON", "order_id": "1", "is_subtract": True})

        assert "address" in exc_info.value.errors

    async def test_create_auth_error(self):
        async with make_payout({"message": "Unauthenticated."}, 401) as payout:
            with pytest.raises(AuthenticationError):
                await payout.create({"amount": "5", "currency": "USDT", "network": "TRON", "order_id": "1", "address": "TExampleAddr2", "is_subtract": True})

    async def test_create_connection_error(self):
        def handler(r: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("timeout")

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.heleket.com/"
        )
        async with AsyncPayout(PAYOUT_KEY, MERCHANT_UUID, http_client=client) as payout:
            with pytest.raises(ConnectionError):
                await payout.create({"amount": "5", "currency": "USDT", "network": "TRON", "order_id": "1", "address": "TExampleAddr2", "is_subtract": True})

    async def test_create_api_error(self):
        async with make_payout({"state": 1, "message": "Payout service not found"}) as payout:
            with pytest.raises(APIError) as exc_info:
                await payout.create({"amount": "5", "currency": "INVALID", "network": "TRON", "order_id": "1", "address": "TExampleAddr2", "is_subtract": True})

        assert "Payout service not found" in str(exc_info.value)


@pytest.mark.unit
class TestAsyncPayoutInfo:
    async def test_info_by_uuid(self):
        result_data = {"uuid": "a7c0caec", "status": "process", "is_final": False}
        async with make_payout({"state": 0, "result": result_data}) as payout:
            result = await payout.info({"uuid": "a7c0caec"})

        assert result["uuid"] == "a7c0caec"

    async def test_info_by_order_id(self):
        result_data = {"uuid": "a7c0caec", "order_id": "payout_1", "status": "paid"}
        async with make_payout({"state": 0, "result": result_data}) as payout:
            result = await payout.info({"order_id": "payout_1"})

        assert result["order_id"] == "payout_1"

    async def test_info_validation_error(self):
        async with make_payout(
            {"state": 1, "errors": {"uuid": ["validation.required_without"], "order_id": ["validation.required_without"]}},
            422,
        ) as payout:
            with pytest.raises(ValidationError):
                await payout.info({})

    async def test_info_auth_error(self):
        async with make_payout({"message": "Unauthenticated."}, 401) as payout:
            with pytest.raises(AuthenticationError):
                await payout.info({"order_id": "1"})
