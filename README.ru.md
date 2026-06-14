# Heleket Python SDK

[🇬🇧 English](README.md) | 🇷🇺 Русский

> **Это неофициальный SDK, созданный сообществом. Он не аффилирован с Heleket и не поддерживается командой Heleket.**
> Официальная документация API: [doc.heleket.com](https://doc.heleket.com)

Неофициальный Python SDK для платёжного шлюза [Heleket](https://heleket.com).
Реализует полный набор методов официального PHP SDK с исправлениями и улучшениями.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Содержание

- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [Использование в Django](#использование-в-django)
- [Методы Payment](#методы-payment)
- [Методы Payout](#методы-payout)
- [Обработка ошибок](#обработка-ошибок)
- [Верификация webhook](#верификация-webhook)
- [Тесты](#тесты)

---

## Установка

```bash
pip install git+https://github.com/SmilingHemp/heleket-python-sdk.git
```

Или скопируй папку `heleket/` напрямую в свой проект — внешних зависимостей нет, только стандартная библиотека Python.

---

## Быстрый старт

```python
from heleket import Client, HeleketError, ValidationError, AuthenticationError

payment = Client.payment("your_payment_api_key", "your_merchant_uuid")

try:
    result = payment.create({
        "amount": "15",
        "currency": "USD",
        "order_id": "order_001",
    })
    print(result["url"])  # ссылка на страницу оплаты
except ValidationError as e:
    print("Ошибка валидации:", e.errors)
except AuthenticationError:
    print("Неверный API ключ")
except HeleketError as e:
    print("Ошибка:", e)
```

---

## Использование в Django

### settings.py

```python
HELEKET_PAYMENT_KEY   = "your_payment_api_key"
HELEKET_PAYOUT_KEY    = "your_payout_api_key"
HELEKET_MERCHANT_UUID = "your_merchant_uuid"
```

### Создание платежа

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

### Webhook в Django view

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

    # sign приходит в теле webhook, не в заголовке
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

    # твоя логика обработки
    return HttpResponse("OK")
```

---

## Методы Payment

Создание экземпляра:

```python
payment = Client.payment(payment_key, merchant_uuid)
# или напрямую:
from heleket import Payment
payment = Payment(payment_key, merchant_uuid)
```

### `payment.create(data)` — создать инвойс

```python
result = payment.create({
    # Обязательные
    "amount":   "15",     # сумма (строка, разделитель дробной части — точка)
    "currency": "USD",    # код валюты
    "order_id": "ord_1",  # уникальный ID в вашей системе (alphanum, _, -)

    # Опциональные
    "network":                 "tron",    # код сети (если нужна конкретная)
    "to_currency":             "USDT",    # криптовалюта для конвертации
    "url_callback":            "https://your.site/webhook/",
    "url_return":              "https://your.site/cancel/",
    "url_success":             "https://your.site/success/",
    "is_payment_multiple":     True,      # разрешить доплату
    "lifetime":                3600,      # время жизни инвойса в секундах (300–43200)
    "subtract":                0,         # % комиссии на плательщика (0–100)
    "accuracy_payment_percent": 0,        # допустимая погрешность оплаты (0–5)
    "discount_percent":        5,         # скидка (>0) или доп. комиссия (<0)
    "additional_data":         "user:42", # произвольная строка до 255 символов
    "currencies":     [{"currency": "USDT", "network": "tron"}],  # белый список валют
    "except_currencies": [{"currency": "BTC"}],                   # чёрный список
    "course_source":  "Binance",  # источник курса: Binance, BinanceP2P, Exmo, Kucoin
    "from_referral_code": "REF123",
    "is_refresh":     False,      # обновить просроченный инвойс по order_id
    "payer_email":    "user@example.com",
})

# result содержит:
# uuid, order_id, amount, payer_amount, payer_currency, currency,
# network, address, url, payment_status, expired_at, is_final,
# created_at, updated_at, address_qr_code, commission, ...
```

### `payment.info(data)` — информация о платеже

```python
result = payment.info({"uuid": "70b8db5c-..."})
# или
result = payment.info({"order_id": "ord_1"})
# если переданы оба — идентификация по order_id
```

### `payment.history(cursor, parameters)` — история платежей

```python
# Первая страница
result = payment.history()

# Фильтрация по дате (формат: YYYY-MM-DD H:mm:ss)
result = payment.history(parameters={
    "date_from": "2024-01-01 00:00:00",
    "date_to":   "2024-01-31 23:59:59",
})

# Следующая страница
next_cursor = result["paginate"]["nextCursor"]
result = payment.history(cursor=next_cursor)

# result содержит:
# items    — список платежей
# paginate — { count, hasPages, nextCursor, previousCursor, perPage }
```

### `payment.balance()` — баланс мерчанта

```python
result = payment.balance()
# result — список объектов с balance.merchant и balance.user
```

### `payment.services()` — доступные сервисы

```python
result = payment.services()
# result — список доступных валют и сетей для приёма платежей
```

### `payment.resend_notification(data)` — повторная отправка webhook

```python
payment.resend_notification({"order_id": "ord_1"})
# Работает только для финализированных инвойсов: paid, paid_over, wrong_amount
# Максимум 10 повторных отправок
```

### `payment.create_wallet(data)` — статический кошелёк

```python
result = payment.create_wallet({
    # Обязательные
    "currency": "USDT",
    "network":  "tron",
    "order_id": "wallet_user_42",  # макс. 100 символов

    # Опциональные
    "url_callback":      "https://your.site/webhook/",
    "from_referral_code": "REF123",
})

# result содержит:
# wallet_uuid, uuid, order_id, address, network, currency, url
```

---

## Методы Payout

Создание экземпляра:

```python
payout = Client.payout(payout_key, merchant_uuid)
```

### `payout.create(data)` — создать выплату

```python
result = payout.create({
    # Обязательные
    "amount":      "5",
    "currency":    "USDT",
    "network":     "TRON",
    "order_id":    "payout_001",    # уникальный ID (alphanum, _, -, макс. 100)
    "address":     "TExampleAddr2...",   # адрес кошелька получателя
    "is_subtract": True,            # True — комиссия из баланса, False — из суммы

    # Опциональные
    "url_callback":   "https://your.site/webhook/",
    "to_currency":    "USDT",     # криптовалюта выплаты (если currency — фиат)
    "course_source":  "Binance",  # Binance, BinanceP2p, Exmo, Kucoin
    "from_currency":  "USDT",     # конвертация из (только USDT)
    "priority":       "recommended",  # recommended | economy | high | highest
    "memo":           "12345",    # для TON-сети
})
```

### `payout.info(data)` — информация о выплате

```python
result = payout.info({"uuid": "a7c0caec-..."})
# или
result = payout.info({"order_id": "payout_001"})
```

---

## Обработка ошибок

Все исключения наследуются от `HeleketError`:

```
HeleketError
├── APIError              # HTTP ошибки от сервера (status_code, uri)
│   └── ValidationError   # 422 — ошибки валидации полей (errors)
├── AuthenticationError   # 401 — неверный API ключ
└── ConnectionError       # сетевые ошибки, таймауты
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
    # e.errors — словарь: {"amount": ["validation.required"], ...}
    print(e.errors)
except AuthenticationError:
    # неверный payment_key
    pass
except ConnectionError:
    # нет сети или таймаут
    pass
except APIError as e:
    # e.status_code — HTTP код
    # e.uri — эндпоинт
    print(e.status_code, e.uri, e)
except HeleketError:
    # любая другая ошибка SDK
    pass
```

---

## Верификация webhook

Heleket отправляет `sign` в теле webhook-запроса.

Алгоритм по документации: `sign = md5(base64_encode(json_body_без_sign) + payment_key)`

> **Важно:** PHP экранирует слэши в JSON (`/` → `\/`). SDK воспроизводит это поведение автоматически.

```python
# sign находится в теле запроса, не в заголовке
data = json.loads(request.body)
sign = data.get("sign", "")

if payment.verify_webhook(request.body, sign):
    # подпись валидна — запрос от Heleket
    pass
```

Дополнительно рекомендуется ограничить `url_callback` по IP из официальной документации Heleket.

---

## Тесты

```bash
# Установить зависимости
pip install git+https://github.com/SmilingHemp/heleket-python-sdk.git
pip install pytest

# Запустить unit-тесты (без сети)
pytest -m "not integration" -v

# Запустить integration-тесты (требуют реальные API ключи)
pytest -m integration -v
```

---

## Лицензия

[MIT](LICENSE) — используй свободно в любых проектах.
