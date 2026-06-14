from __future__ import annotations

import base64
import hashlib
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from heleket._request_builder import RequestBuilder
from heleket.exceptions import APIError, AuthenticationError, ConnectionError, ValidationError
from tests.conftest import MERCHANT_UUID, PAYMENT_KEY, make_error_response, make_response


@pytest.mark.unit
class TestRequestBuilderInit:
    def test_raises_on_empty_key(self):
        with pytest.raises(ValueError):
            RequestBuilder("", MERCHANT_UUID)

    def test_raises_on_empty_uuid(self):
        with pytest.raises(ValueError):
            RequestBuilder(PAYMENT_KEY, "")


@pytest.mark.unit
class TestBuildSign:
    def test_sign_algorithm(self):
        builder = RequestBuilder(PAYMENT_KEY, MERCHANT_UUID)
        body = '{"amount":"10","currency":"USDT"}'
        encoded = base64.b64encode(body.encode()).decode()
        expected = hashlib.md5((encoded + PAYMENT_KEY).encode()).hexdigest()
        assert builder._build_sign(body) == expected

    def test_sign_empty_body(self):
        """Per API docs: sign for empty body uses base64_encode('')."""
        builder = RequestBuilder(PAYMENT_KEY, MERCHANT_UUID)
        body = "{}"
        encoded = base64.b64encode(body.encode()).decode()
        expected = hashlib.md5((encoded + PAYMENT_KEY).encode()).hexdigest()
        assert builder._build_sign(body) == expected


@pytest.mark.unit
class TestSendRequest:
    def test_success_returns_result(self, mock_opener):
        result_data = {"uuid": "abc-123", "url": "https://pay.heleket.com/pay/abc-123"}
        mock_opener.open.return_value = make_response({"state": 0, "result": result_data})

        builder = RequestBuilder(PAYMENT_KEY, MERCHANT_UUID, opener=mock_opener)
        result = builder.send_request("v1/payment", {"amount": "10", "currency": "USDT", "order_id": "1"})

        assert result == result_data

    def test_returns_true_when_result_empty(self, mock_opener):
        mock_opener.open.return_value = make_response({"state": 0, "result": []})

        builder = RequestBuilder(PAYMENT_KEY, MERCHANT_UUID, opener=mock_opener)
        result = builder.send_request("v1/payment/resend", {"order_id": "1"})

        assert result is True

    def test_cursor_appended_to_url(self, mock_opener):
        mock_opener.open.return_value = make_response({"state": 0, "result": {"items": [], "paginate": {}}})

        builder = RequestBuilder(PAYMENT_KEY, MERCHANT_UUID, opener=mock_opener)
        builder.send_request("v1/payment/list", {}, cursor="eyJpZCI6MjEyfQ")

        call_args = mock_opener.open.call_args[0][0]
        assert "?cursor=eyJpZCI6MjEyfQ" in call_args.full_url

    def test_raises_validation_error_on_422_with_errors(self, mock_opener):
        mock_opener.open.side_effect = make_error_response(
            {"state": 1, "errors": {"amount": ["validation.required"]}}, 422
        )
        builder = RequestBuilder(PAYMENT_KEY, MERCHANT_UUID, opener=mock_opener)

        with pytest.raises(ValidationError) as exc_info:
            builder.send_request("v1/payment", {})

        assert exc_info.value.errors == {"amount": ["validation.required"]}
        assert exc_info.value.status_code == 422

    def test_raises_api_error_on_state_1_with_message(self, mock_opener):
        mock_opener.open.return_value = make_response(
            {"state": 1, "message": "The currency was not found"}, 200
        )
        builder = RequestBuilder(PAYMENT_KEY, MERCHANT_UUID, opener=mock_opener)

        with pytest.raises(APIError) as exc_info:
            builder.send_request("v1/payment", {"amount": "10", "currency": "INVALID", "order_id": "1"})

        assert "currency was not found" in str(exc_info.value)

    def test_raises_authentication_error_on_401(self, mock_opener):
        mock_opener.open.side_effect = make_error_response(
            {"message": "Unauthenticated."}, 401
        )
        builder = RequestBuilder(PAYMENT_KEY, MERCHANT_UUID, opener=mock_opener)

        with pytest.raises(AuthenticationError):
            builder.send_request("v1/payment", {})

    def test_raises_connection_error_on_url_error(self, mock_opener):
        mock_opener.open.side_effect = urllib.error.URLError("Connection refused")
        builder = RequestBuilder(PAYMENT_KEY, MERCHANT_UUID, opener=mock_opener)

        with pytest.raises(ConnectionError):
            builder.send_request("v1/payment", {})

    def test_sign_header_is_set_correctly(self, mock_opener):
        mock_opener.open.return_value = make_response({"state": 0, "result": {}})

        builder = RequestBuilder(PAYMENT_KEY, MERCHANT_UUID, opener=mock_opener)
        data = {"amount": "10"}
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        expected_sign = builder._build_sign(body)

        builder.send_request("v1/payment", data)

        req = mock_opener.open.call_args[0][0]
        assert req.get_header("Sign") == expected_sign

    def test_merchant_header_is_set(self, mock_opener):
        mock_opener.open.return_value = make_response({"state": 0, "result": {}})

        builder = RequestBuilder(PAYMENT_KEY, MERCHANT_UUID, opener=mock_opener)
        builder.send_request("v1/payment", {})

        req = mock_opener.open.call_args[0][0]
        assert req.get_header("Merchant") == MERCHANT_UUID
