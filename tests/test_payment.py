from __future__ import annotations

import base64
import hashlib
import json
import urllib.error

import pytest

from heleket.exceptions import APIError, AuthenticationError, ConnectionError, ValidationError
from tests.conftest import PAYMENT_KEY, make_error_response, make_response


@pytest.mark.unit
class TestPaymentCreate:
    def test_create_success(self, payment_client, mock_opener):
        result_data = {
            "uuid": "1ec87133-b22d-4643-988f-cac29a6ac85d",
            "order_id": "order_1",
            "amount": "15.00",
            "url": "https://pay.heleket.com/pay/1ec87133-b22d-4643-988f-cac29a6ac85d",
            "status": "check",
        }
        mock_opener.open.return_value = make_response({"state": 0, "result": result_data})

        result = payment_client.create({"amount": "15", "currency": "USD", "order_id": "order_1"})

        assert result["uuid"] == "1ec87133-b22d-4643-988f-cac29a6ac85d"
        assert result["url"].startswith("https://pay.heleket.com")

    def test_create_validation_error(self, payment_client, mock_opener):
        mock_opener.open.side_effect = make_error_response(
            {"state": 1, "errors": {"amount": ["validation.required"]}}, 422
        )
        with pytest.raises(ValidationError) as exc_info:
            payment_client.create({"currency": "USD", "order_id": "1"})

        assert "amount" in exc_info.value.errors

    def test_create_auth_error(self, payment_client, mock_opener):
        mock_opener.open.side_effect = make_error_response({"message": "Unauthenticated."}, 401)

        with pytest.raises(AuthenticationError):
            payment_client.create({"amount": "15", "currency": "USD", "order_id": "1"})

    def test_create_connection_error(self, payment_client, mock_opener):
        mock_opener.open.side_effect = urllib.error.URLError("timeout")

        with pytest.raises(ConnectionError):
            payment_client.create({"amount": "15", "currency": "USD", "order_id": "1"})

    def test_create_api_error_message(self, payment_client, mock_opener):
        mock_opener.open.return_value = make_response(
            {"state": 1, "message": "The currency was not found"}, 200
        )
        with pytest.raises(APIError) as exc_info:
            payment_client.create({"amount": "15", "currency": "INVALID", "order_id": "1"})

        assert "currency was not found" in str(exc_info.value)


@pytest.mark.unit
class TestPaymentInfo:
    def test_info_by_uuid(self, payment_client, mock_opener):
        result_data = {"uuid": "70b8db5c-b952-406d-af26-4e1c34c27f15", "status": "cancel"}
        mock_opener.open.return_value = make_response({"state": 0, "result": result_data})

        result = payment_client.info({"uuid": "70b8db5c-b952-406d-af26-4e1c34c27f15"})

        assert result["uuid"] == "70b8db5c-b952-406d-af26-4e1c34c27f15"

    def test_info_by_order_id(self, payment_client, mock_opener):
        result_data = {"uuid": "70b8db5c-b952-406d-af26-4e1c34c27f15", "order_id": "order_1"}
        mock_opener.open.return_value = make_response({"state": 0, "result": result_data})

        result = payment_client.info({"order_id": "order_1"})

        assert result["order_id"] == "order_1"

    def test_info_validation_error_no_params(self, payment_client, mock_opener):
        mock_opener.open.side_effect = make_error_response(
            {"state": 1, "errors": {"uuid": ["validation.required_without"], "order_id": ["validation.required_without"]}},
            422,
        )
        with pytest.raises(ValidationError):
            payment_client.info({})


@pytest.mark.unit
class TestPaymentHistory:
    def test_history_no_cursor(self, payment_client, mock_opener):
        paginate = {"count": 2, "hasPages": False, "nextCursor": None, "previousCursor": None, "perPage": 15}
        mock_opener.open.return_value = make_response(
            {"state": 0, "result": {"items": [], "paginate": paginate}}
        )

        result = payment_client.history()

        req = mock_opener.open.call_args[0][0]
        assert "cursor" not in req.full_url

    def test_history_with_cursor_in_url(self, payment_client, mock_opener):
        mock_opener.open.return_value = make_response(
            {"state": 0, "result": {"items": [], "paginate": {}}}
        )
        payment_client.history(cursor="eyJpZCI6MjEyfQ")

        req = mock_opener.open.call_args[0][0]
        assert "?cursor=eyJpZCI6MjEyfQ" in req.full_url

    def test_history_with_date_filters(self, payment_client, mock_opener):
        mock_opener.open.return_value = make_response(
            {"state": 0, "result": {"items": [], "paginate": {}}}
        )
        payment_client.history(parameters={"date_from": "2023-05-04 00:00:00", "date_to": "2023-05-16 23:59:59"})

        req = mock_opener.open.call_args[0][0]
        body = json.loads(req.data.decode())
        assert body["date_from"] == "2023-05-04 00:00:00"

    def test_history_api_error(self, payment_client, mock_opener):
        mock_opener.open.side_effect = make_error_response(
            {"state": 1, "errors": {"date_from": ["validation.regex"]}}, 422
        )
        with pytest.raises(ValidationError):
            payment_client.history(parameters={"date_from": "bad-format"})


@pytest.mark.unit
class TestPaymentBalance:
    def test_balance_success(self, payment_client, mock_opener):
        result_data = [{"balance": {"merchant": [{"uuid": "abc", "balance": "5.00", "currency_code": "USDT"}], "user": []}}]
        mock_opener.open.return_value = make_response({"state": 0, "result": result_data})

        result = payment_client.balance()

        assert isinstance(result, list)

    def test_balance_auth_error(self, payment_client, mock_opener):
        mock_opener.open.side_effect = make_error_response({"message": "Unauthenticated."}, 401)

        with pytest.raises(AuthenticationError):
            payment_client.balance()


@pytest.mark.unit
class TestPaymentResendNotification:
    def test_resend_success(self, payment_client, mock_opener):
        mock_opener.open.return_value = make_response({"state": 0, "result": []})

        result = payment_client.resend_notification({"order_id": "order_1"})

        assert result is True

    def test_resend_not_found(self, payment_client, mock_opener):
        mock_opener.open.return_value = make_response({"state": 1, "message": "Payment not found"})

        with pytest.raises(APIError) as exc_info:
            payment_client.resend_notification({"order_id": "nonexistent"})

        assert "Payment not found" in str(exc_info.value)


@pytest.mark.unit
class TestPaymentCreateWallet:
    def test_create_wallet_success(self, payment_client, mock_opener):
        result_data = {
            "wallet_uuid": "de15b0f6-883f-4585-b27b-73a648044a92",
            "uuid": "87961ae5-80c5-413a-a4fe-d38199894940",
            "order_id": "wallet_1",
            "address": "TExampleAddr1000000000000000000000",
            "network": "tron",
            "currency": "USDT",
            "url": "https://pay.heleket.com/wallet/3901446a-4b74-4796-b50a-14e14dafe3ed",
        }
        mock_opener.open.return_value = make_response({"state": 0, "result": result_data})

        result = payment_client.create_wallet({
            "currency": "USDT",
            "network": "tron",
            "order_id": "wallet_1",
            "url_callback": "https://your.site/callback",
        })

        assert result["address"] == "TExampleAddr1000000000000000000000"
        assert result["wallet_uuid"] == "de15b0f6-883f-4585-b27b-73a648044a92"

    def test_create_wallet_validation_error(self, payment_client, mock_opener):
        mock_opener.open.side_effect = make_error_response(
            {"state": 1, "errors": {"currency": ["validation.required"]}}, 422
        )
        with pytest.raises(ValidationError):
            payment_client.create_wallet({"network": "tron", "order_id": "1"})


@pytest.mark.unit
class TestVerifyWebhook:
    """
    Tests for webhook signature verification.
    Simulates webhooks as sent by the test-webhook endpoint from the API docs.
    Algorithm: md5(base64_encode(json_body_without_sign) + payment_key)
    PHP escapes slashes in JSON — we must replicate that.
    """

    def _make_webhook_payload(self, data: dict) -> tuple[str, str]:
        """Generate a valid signed webhook payload, replicating PHP json_encode behavior."""
        sign_data = {k: v for k, v in data.items()}
        # PHP escapes forward slashes in JSON strings
        body = json.dumps(sign_data, ensure_ascii=False, separators=(",", ":")).replace("/", "\\/")
        encoded = base64.b64encode(body.encode("utf-8")).decode("utf-8")
        sign = hashlib.md5((encoded + PAYMENT_KEY).encode("utf-8")).hexdigest()

        payload_data = dict(data)
        payload_data["sign"] = sign
        payload = json.dumps(payload_data, ensure_ascii=False, separators=(",", ":"))
        return payload, sign

    def test_verify_webhook_valid_paid(self, payment_client):
        """Simulates a 'paid' webhook from test-webhook/payment endpoint."""
        data = {
            "type": "payment",
            "uuid": "62f88b36-a9d5-4fa6-aa26-e040c3dbf26d",
            "order_id": "order_1",
            "amount": "3.00000000",
            "payment_amount": "3.00000000",
            "status": "paid",
            "network": "tron",
            "currency": "TRX",
        }
        payload, sign = self._make_webhook_payload(data)

        assert payment_client.verify_webhook(payload, sign) is True

    def test_verify_webhook_valid_bytes(self, payment_client):
        """Verify works with bytes payload (as from Django request.body)."""
        data = {"type": "payment", "uuid": "abc-123", "status": "paid", "order_id": "1"}
        payload, sign = self._make_webhook_payload(data)

        assert payment_client.verify_webhook(payload.encode("utf-8"), sign) is True

    def test_verify_webhook_with_slash_in_txid(self, payment_client):
        """
        Critical: PHP escapes slashes, Python does not by default.
        txid with slash must produce correct signature.
        Per API docs warning about JS vs PHP encoding difference.
        """
        data = {
            "type": "payment",
            "uuid": "62f88b36-a9d5-4fa6-aa26-e040c3dbf26d",
            "order_id": "order_slash",
            "amount": "20",
            "currency": "USDT",
            "network": "tron",
            "txid": "someTxidWith/Slash",
            "status": "paid",
        }
        payload, sign = self._make_webhook_payload(data)

        assert payment_client.verify_webhook(payload, sign) is True

    def test_verify_webhook_invalid_sign(self, payment_client):
        data = {"type": "payment", "uuid": "abc", "status": "paid", "order_id": "1"}
        payload, _ = self._make_webhook_payload(data)

        assert payment_client.verify_webhook(payload, "invalidsignature000000000000000") is False

    def test_verify_webhook_tampered_payload(self, payment_client):
        """Tampering with amount after signing must fail verification."""
        data = {"type": "payment", "uuid": "abc", "amount": "10.00", "status": "paid", "order_id": "1"}
        payload, sign = self._make_webhook_payload(data)

        tampered = payload.replace('"amount":"10.00"', '"amount":"999.00"')
        assert payment_client.verify_webhook(tampered, sign) is False

    def test_verify_webhook_invalid_json(self, payment_client):
        assert payment_client.verify_webhook("not-json", "anysign") is False

    def test_verify_webhook_cancel_status(self, payment_client):
        """Test webhook with cancel status — same signing algorithm."""
        data = {
            "type": "payment",
            "uuid": "e1830f1b-50fc-432e-80ec-15b58ccac867",
            "currency": "ETH",
            "network": "eth",
            "status": "cancel",
            "order_id": "test_order",
        }
        payload, sign = self._make_webhook_payload(data)

        assert payment_client.verify_webhook(payload, sign) is True


@pytest.mark.unit
class TestPaymentServices:
    def test_services_success(self, payment_client, mock_opener):
        mock_opener.open.return_value = make_response({"state": 0, "result": [{"network": "tron", "currency": "USDT"}]})

        result = payment_client.services()

        assert isinstance(result, list)
