from __future__ import annotations

from typing import Any

SECRET_KEYS = ("api_key", "token", "password", "secret", "private_key")


def redact_secrets(value: Any, extra_fields: list[str] | None = None) -> Any:
    extra_fields = extra_fields or []
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _is_secret_key(key, extra_fields) else redact_secrets(item, extra_fields)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item, extra_fields) for item in value]
    return value


def _is_secret_key(key: str, extra_fields: list[str]) -> bool:
    lowered = key.lower()
    return lowered in {field.lower() for field in extra_fields} or any(marker in lowered for marker in SECRET_KEYS)
