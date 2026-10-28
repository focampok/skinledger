"""Structured event log: one stdout line per event, never a secret or a signed URL."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from typing import Any

from skinledger.config import get_settings
from skinledger.usage import GUATEMALA_TZ

EVENT_LOGGER = "skinledger.events"
REDACTED = "<redacted>"
MAX_VALUE_CHARS = 200

_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "error": logging.ERROR,
}

# Field names that must never reach the log, whatever the caller passes.
_BLOCKED_KEYS = frozenset(
    {
        "admin_token",
        "api_key",
        "authorization",
        "body",
        "cookie",
        "cookies",
        "display_name",
        "image",
        "image_bytes",
        "invite_code",
        "name",
        "owner_token",
        "owner_token_hash",
        "password",
        "photo",
        "secret",
        "token",
        "youcam_api_key",
    }
)

_SIGNED_URL_RE = re.compile(r"(https?://[^\s?#]+)\?[^\s]*")
_CONTROL_RE = re.compile(r"[\r\n\t]+")

_configured = False


def configure_logging(level: str | None = None) -> None:
    """Send event lines to stdout once; safe to call many times and from tests."""
    global _configured
    logger = logging.getLogger(EVENT_LOGGER)
    logger.setLevel(_level(level))
    # Keep propagation on so pytest's caplog and any root handler still see events.
    logger.propagate = True
    if not any(getattr(handler, "_skinledger_event", False) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler._skinledger_event = True  # type: ignore[attr-defined]
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    _configured = True


def _level(name: str | None) -> int:
    if name:
        return _LEVELS.get(str(name).lower(), logging.INFO)
    try:
        configured = get_settings().log_level
    except Exception:  # pragma: no cover - configuration must never break logging
        configured = "INFO"
    return _LEVELS.get(str(configured).lower(), logging.INFO)


def _is_blocked(key: str) -> bool:
    lowered = key.lower()
    if lowered in _BLOCKED_KEYS:
        return True
    if "cookie" in lowered:
        return True
    if lowered.endswith(("_token", "_secret", "_api_key")):
        return True
    return False


def _secret_values() -> tuple[str, ...]:
    """Configured secrets, so an accidental interpolation is still redacted."""
    try:
        settings = get_settings()
    except Exception:  # pragma: no cover - logging must never fail
        return ()
    values: list[str] = []
    for attribute in ("youcam_api_key", "invite_code", "admin_token"):
        secret = getattr(settings, attribute, None)
        if secret is None:
            continue
        value = secret.get_secret_value() if hasattr(secret, "get_secret_value") else str(secret)
        if value:
            values.append(value)
    return tuple(values)


def _redact_text(text: str) -> str:
    text = _CONTROL_RE.sub(" ", text)
    for secret in _secret_values():
        if secret in text:
            text = text.replace(secret, REDACTED)
    # Download URLs expire and carry a signature; keep only the path.
    text = _SIGNED_URL_RE.sub(r"\1?<signed>", text)
    if len(text) > MAX_VALUE_CHARS:
        text = text[: MAX_VALUE_CHARS - 3] + "..."
    return text


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "-"
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    text = _redact_text(str(value))
    if not text:
        return '""'
    if any(character in text for character in ' "='):
        return json.dumps(text, ensure_ascii=False)
    return text


def log_event(event: str, *, level: str | int = "info", **fields: Any) -> None:
    """Write one line: ts LEVEL event key=value ... (ts in America/Guatemala)."""
    if not _configured:
        configure_logging()
    numeric_level = level if isinstance(level, int) else _LEVELS.get(level.lower(), logging.INFO)
    if not logging.getLogger(EVENT_LOGGER).isEnabledFor(numeric_level):
        return

    parts = [
        datetime.now(GUATEMALA_TZ).isoformat(timespec="seconds"),
        logging.getLevelName(numeric_level),
        event,
    ]
    for key, value in fields.items():
        if _is_blocked(str(key)):
            parts.append(f"{key}={REDACTED}")
            continue
        parts.append(f"{key}={_format_value(value)}")
    logging.getLogger(EVENT_LOGGER).log(numeric_level, " ".join(parts))


def mode_name(*, mock: bool) -> str:
    """The analysis mode recorded with every capture event."""
    return "mock" if mock else "real"
