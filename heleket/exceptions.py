"""Exception hierarchy for the Heleket SDK.

All exceptions inherit from HeleketError so callers can catch
either the base class or a specific subclass:

    HeleketError
    ├── APIError              # HTTP error response from the server
    │   └── ValidationError   # 422 with per-field error details
    ├── AuthenticationError   # 401 — invalid API key
    └── ConnectionError       # network failure or timeout
"""
from __future__ import annotations

from typing import Any


class HeleketError(Exception):
    """Base — catch for any SDK error."""


class APIError(HeleketError):
    """HTTP errors from the server."""

    def __init__(self, message: str, status_code: int, uri: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.uri = uri


class ValidationError(APIError):
    """422 — validation errors with field details."""

    def __init__(self, message: str, uri: str, errors: dict[str, Any]) -> None:
        super().__init__(message, 422, uri)
        self.errors = errors


class AuthenticationError(HeleketError):
    """401 — invalid API key."""


class ConnectionError(HeleketError):  # noqa: A001
    """Network errors, timeouts."""
