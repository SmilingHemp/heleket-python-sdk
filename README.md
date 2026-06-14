# Heleket Python SDK

🇷🇺 [Русский](README.ru.md) | [🇬🇧 English](#)

> **This is an unofficial community SDK. It is not affiliated with or supported by Heleket.**
> Official API documentation: [doc.heleket.com](https://doc.heleket.com)

Unofficial Python SDK for the [Heleket](https://heleket.com) payment gateway.
Covers the full method set of the official PHP SDK with fixes and improvements.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Table of contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Django integration](#django-integration)
- [Payment methods](#payment-methods)
- [Payout methods](#payout-methods)
- [Error handling](#error-handling)
- [Webhook verification](#webhook-verification)
- [Tests](#tests)

---

## Installation

```bash
pip install -e path/to/python-sdk
```

Or copy the `heleket/` folder directly into your project — no external dependencies, stdlib only.

---

## Quick start

```python
from heleket import Client, HeleketError, ValidationError, AuthenticationError

payment = Client.payment("your_payment_api_key", "your_merchant_uuid")

try:
    result = payment.create({
        "amount": "15",
        "currency": "USD",
        "order_id": "order_001",
    })
    print(result["url"])  # redirect user to this payment page URL
except ValidationError as e:
    print("Validation error:", e.errors)
except AuthenticationError:
    print("Invalid API key")
except HeleketError as e:
    print("Error:", e)
```

---

## Django integration

### settings.py

```python
HELEKET_PAYMENT_KEY   = "your_payment_api_key"
HELEKET_PAYOUT_KEY    = "your_payout_api_key"
HELEKET_MERCHANT_UUID = "your_merchant_uuid"
```

### Create a payment

```python
from django.conf import settings
from heleket import Client, HeleketError, ValidationError

payment = Client.payment(settings.HELEKET_PAYMENT_KEY, settings.HELEKET_MERCHANT_UUID)

result = payment.create({
    "amount": "15",
    "currency": "USD",
    "order_id": "order_001",
    "url_callback": "https://your.site/webhook/heleket/",
    "url_return": "https://your.site/cancel/",
    "url_success": "https://your.site/success/",
})
pay_url = result["url"]
```

### Webhook view

```python
# views.py
import json
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from heleket import Client

@csrf_exempt
def heleket_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    # sign is inside the request body, not in headers
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    sign = data.get("sign", "")
    payment = Client.payment(settings.HELEKET_PAYMENT_KEY, settings.HELEKET_MERCHANT_UUID)

    if not payment.verify_webhook(request.body, sign):
        return HttpResponseForbidden("Invalid signature")

    status   = data.get("status")    # paid | cancel | wrong_amount | paid_over | ...
    order_id = data.get("order_id")

    # your processing logic here
    return HttpResponse("OK")
```

---

## Payment methods

Create an instance:

```python
payment = Client.payment(payment_key, merchant_uuid)
# or directly:
from heleket import Payment
payment = Payment(payment_key, merchant_uuid)
```

### `payment.create(data)` — create an invoice

```python
result = payment.create({
    # Required
    "amount":   "15",     # string, decimal separator is a dot
    "currency": "USD",    # currency code
    "order_id": "ord_1",  # unique ID in your system (alphanum, _, -)

    # Optional
    "network":                  "tron",    # blockchain network code
    "to_currency":              "USDT",    # target crypto for conversion
    "url_callback":             "https://your.site/webhook/",
    "url_return":               "https://your.site/cancel/",
    "url_success":              "https://your.site/success/",
    "is_payment_multiple":      True,      # allow partial payments
    "lifetime":                 3600,      # invoice TTL in seconds (300–43200)
    "subtract":                 0,         # % of commission charged to payer (0–100)
    "accuracy_payment_percent": 0,         # acceptable underpayment percent (0–5)
    "discount_percent":         5,         # discount (>0) or extra commission (<0)
    "additional_data":          "user:42", # arbitrary string up to 255 chars
    "currencies":     [{"currency": "USDT", "network": "tron"}],  # allowlist
    "except_currencies": [{"currency": "BTC"}],                   # denylist
    "course_source":  "Binance",  # Binance | BinanceP2P | Exmo | Kucoin
    "from_referral_code": "REF123",
    "is_refresh":     False,      # refresh an expired invoice by order_id
    "payer_email":    "user@example.com",
})

# result contains:
# uuid, order_id, amount, payer_amount, payer_currency, currency,
# network, address, url, payment_status, expired_at, is_final,
# created_at, updated_at, address_qr_code, commission, ...
```

### `payment.info(data)` — get payment info

```python
result = payment.info({"uuid": "70b8db5c-..."})
# or
result = payment.info({"order_id": "ord_1"})
# if both passed — identified by order_id
```

### `payment.history(cursor, parameters)` — payment list

```python
# First page
result = payment.history()

# Filter by date (format: YYYY-MM-DD H:mm:ss)
result = payment.history(parameters={
    "date_from": "2024-01-01 00:00:00",
    "date_to":   "2024-01-31 23:59:59",
})

# Next page
next_cursor = result["paginate"]["nextCursor"]
result = payment.history(cursor=next_cursor)

# result contains:
# items    — list of payments
# paginate — { count, hasPages, nextCursor, previousCursor, perPage }
```

### `payment.balance()` — merchant balance

```python
result = payment.balance()
# result — list with balance.merchant and balance.user arrays
```

### `payment.services()` — available services

```python
result = payment.services()
# result — list of supported currencies and networks
```

### `payment.resend_notification(data)` — resend webhook

```python
payment.resend_notification({"order_id": "ord_1"})
# Only works for finalized invoices: paid, paid_over, wrong_amount
# Maximum 10 resends per invoice
```

### `payment.create_wallet(data)` — static wallet

```python
result = payment.create_wallet({
    # Required
    "currency": "USDT",
    "network":  "tron",
    "order_id": "wallet_user_42",  # max 100 chars

    # Optional
    "url_callback":       "https://your.site/webhook/",
    "from_referral_code": "REF123",
})

# result contains:
# wallet_uuid, uuid, order_id, address, network, currency, url
```

---

## Payout methods

Create an instance:

```python
payout = Client.payout(payout_key, merchant_uuid)
```

### `payout.create(data)` — create a payout

```python
result = payout.create({
    # Required
    "amount":      "5",
    "currency":    "USDT",
    "network":     "TRON",
    "order_id":    "payout_001",   # unique ID (alphanum, _, -, max 100)
    "address":     "TExampleAddr2...",  # recipient wallet address
    "is_subtract": True,           # True — fee from balance, False — fee from amount

    # Optional
    "url_callback":  "https://your.site/webhook/",
    "to_currency":   "USDT",          # target crypto (when currency is fiat)
    "course_source": "Binance",       # Binance | BinanceP2p | Exmo | Kucoin
    "from_currency": "USDT",          # convert from (only USDT supported)
    "priority":      "recommended",   # recommended | economy | high | highest
    "memo":          "12345",         # for TON network
})
```

### `payout.info(data)` — get payout info

```python
result = payout.info({"uuid": "a7c0caec-..."})
# or
result = payout.info({"order_id": "payout_001"})
```

---

## Error handling

All exceptions inherit from `HeleketError`:

```
HeleketError
├── APIError              # HTTP error from the server (status_code, uri)
│   └── ValidationError   # 422 — per-field validation errors (errors)
├── AuthenticationError   # 401 — invalid API key
└── ConnectionError       # network failure or timeout
```

```python
from heleket import (
    HeleketError,
    APIError,
    ValidationError,
    AuthenticationError,
    ConnectionError,
)

try:
    result = payment.create(data)
except ValidationError as e:
    # e.errors — dict: {"amount": ["validation.required"], ...}
    print(e.errors)
except AuthenticationError:
    # wrong payment_key
    pass
except ConnectionError:
    # no network or timeout
    pass
except APIError as e:
    # e.status_code — HTTP status code
    # e.uri — endpoint path
    print(e.status_code, e.uri, e)
except HeleketError:
    # any other SDK error
    pass
```

---

## Webhook verification

Heleket sends `sign` inside the webhook request body.

Algorithm per API docs: `sign = md5(base64_encode(json_body_without_sign) + payment_key)`

> **Note:** PHP escapes forward slashes in JSON (`/` → `\/`). The SDK replicates this automatically.

```python
# sign is in the request body, not in headers
data = json.loads(request.body)
sign = data.get("sign", "")

if payment.verify_webhook(request.body, sign):
    # signature is valid — request is from Heleket
    pass
```

You can also whitelist the Heleket webhook IP listed in the official Heleket documentation.

---

## Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run unit tests (no network required)
pytest -m "not integration" -v

# Run integration tests (require real API keys)
pytest -m integration -v
```

---

## License

[MIT](LICENSE) — free to use in any project.
