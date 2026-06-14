from __future__ import annotations

import urllib.error

import pytest

from heleket.exceptions import APIError, AuthenticationError, ConnectionError, ValidationError
from tests.conftest import make_error_response, make_response


@pytest.mark.unit
class TestPayoutCreate:
    def test_create_success(self, payout_client, mock_opener):
        result_data = {
            "uuid": "a7c0caec-a594-4aaa-b1c4-77d511857594",
            "amount": "5",
            "currency": "USDT",
            "network": "TRON",
            "address": "TExampleAddr2000000000000000000000",
            "status": "process",
        }
        mock_opener.open.return_value = make_response({"state": 0, "result": result_data})

        result = payout_client.create({
            "amount": "5",
            "currency": "USDT",
            "network": "TRON",
            "order_id": "payout_1",
            "address": "TExampleAddr2000000000000000000000",
            "is_subtract": True,
        })

        assert result["uuid"] == "a7c0caec-a594-4aaa-b1c4-77d511857594"
        assert result["status"] == "process"

    def test_create_validation_error(self, payout_client, mock_opener):
        mock_opener.open.side_effect = make_error_response(
            {"state": 1, "errors": {"address": ["validation.required"]}}, 422
        )
        with pytest.raises(ValidationError) as exc_info:
            payout_client.create({"amount": "5", "currency": "USDT", "network": "TRON", "order_id": "1", "is_subtract": True})

        assert "address" in exc_info.value.errors

    def test_create_auth_error(self, payout_client, mock_opener):
        mock_opener.open.side_effect = make_error_response({"message": "Unauthenticated."}, 401)

        with pytest.raises(AuthenticationError):
            payout_client.create({"amount": "5", "currency": "USDT", "network": "TRON", "order_id": "1", "address": "TExampleAddr2", "is_subtract": True})

    def test_create_connection_error(self, payout_client, mock_opener):
        mock_opener.open.side_effect = urllib.error.URLError("timeout")

        with pytest.raises(ConnectionError):
            payout_client.create({"amount": "5", "currency": "USDT", "network": "TRON", "order_id": "1", "address": "TExampleAddr2", "is_subtract": True})

    def test_create_api_error(self, payout_client, mock_opener):
        mock_opener.open.return_value = make_response(
            {"state": 1, "message": "Payout service not found"}, 200
        )
        with pytest.raises(APIError) as exc_info:
            payout_client.create({"amount": "5", "currency": "INVALID", "network": "TRON", "order_id": "1", "address": "TExampleAddr2", "is_subtract": True})

        assert "Payout service not found" in str(exc_info.value)


@pytest.mark.unit
class TestPayoutInfo:
    def test_info_by_uuid(self, payout_client, mock_opener):
        result_data = {
            "uuid": "a7c0caec-a594-4aaa-b1c4-77d511857594",
            "amount": "3",
            "currency": "USDT",
            "network": "TRON",
            "status": "process",
            "is_final": False,
        }
        mock_opener.open.return_value = make_response({"state": 0, "result": result_data})

        result = payout_client.info({"uuid": "a7c0caec-a594-4aaa-b1c4-77d511857594"})

        assert result["uuid"] == "a7c0caec-a594-4aaa-b1c4-77d511857594"
        assert result["is_final"] is False

    def test_info_by_order_id(self, payout_client, mock_opener):
        result_data = {"uuid": "a7c0caec", "order_id": "payout_1", "status": "paid"}
        mock_opener.open.return_value = make_response({"state": 0, "result": result_data})

        result = payout_client.info({"order_id": "payout_1"})

        assert result["order_id"] == "payout_1"

    def test_info_validation_error_no_params(self, payout_client, mock_opener):
        mock_opener.open.side_effect = make_error_response(
            {"state": 1, "errors": {"uuid": ["validation.required_without"], "order_id": ["validation.required_without"]}},
            422,
        )
        with pytest.raises(ValidationError):
            payout_client.info({})

    def test_info_auth_error(self, payout_client, mock_opener):
        mock_opener.open.side_effect = make_error_response({"message": "Unauthenticated."}, 401)

        with pytest.raises(AuthenticationError):
            payout_client.info({"order_id": "1"})
