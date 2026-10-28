"""Structured event log: stdout text plus JSON lines, never a secret or a signed URL."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from skinledger.config import get_settings
from skinledger.usage import GUATEMALA_TZ

EVENT_LOGGER = "skinledger.events"
LOG_FILE_NAME = "skinledger.jsonl"
MAX_LOG_BYTES = 1024 * 1024
LOG_BACKUPS = 3
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
_file_handler: RotatingFileHandler | None = None
_file_handler_path: Path | None = None


class _JsonFormatter(logging.Formatter):
    """One JSON object per line, built from the already-sanitized event payload."""

    def format(self, record: logging.LogRecord) -> str:
        payload = getattr(record, "event_json", None)
        if not isinstance(payload, dict):
            return record.getMessage()
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str | None = None) -> None:
    """Send event lines to stdout and to the rotating JSON-lines file; idempotent."""
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
    _configure_file_handler(logger)
    _configured = True


def _level(name: str | None) -> int:
    if name:
        return _LEVELS.get(str(name).lower(), logging.INFO)
    try:
        configured = get_settings().log_level
    except Exception:  # pragma: no cover - configuration must never break logging
        configured = "INFO"
    return _LEVELS.get(str(configured).lower(), logging.INFO)


def _log_path() -> Path | None:
    """The JSON-lines path, or None when LOG_DIR would sit inside DATA_DIR."""
    try:
        settings = get_settings()
        log_dir = Path(settings.log_dir)
        data_dir = Path(settings.data_dir)
    except Exception:  # pragma: no cover - configuration must never break logging
        return None
    try:
        log_dir.resolve().relative_to(data_dir.resolve())
    except ValueError:
        return log_dir / LOG_FILE_NAME
    except OSError:
        return None
    # Event logs never live on the data volume, even if someone points LOG_DIR there.
    return None


def _configure_file_handler(logger: logging.Logger) -> None:
    global _file_handler, _file_handler_path
    path = _log_path()
    if path is None:
        if _file_handler is not None:
            logger.removeHandler(_file_handler)
            _file_handler.close()
            _file_handler = None
            _file_handler_path = None
        return
    if _file_handler is not None and _file_handler_path == path:
        return
    if _file_handler is not None:
        logger.removeHandler(_file_handler)
        _file_handler.close()
        _file_handler = None
        _file_handler_path = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            path,
            maxBytes=MAX_LOG_BYTES,
            backupCount=LOG_BACKUPS,
            encoding="utf-8",
        )
    except OSError:
        return
    handler.setFormatter(_JsonFormatter())
    handler._skinledger_json = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    _file_handler = handler
    _file_handler_path = path


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


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if value is None:
        return None
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    return _redact_text(str(value))


def _sanitize_fields(fields: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in fields.items():
        name = str(key)
        if _is_blocked(name):
            sanitized[name] = REDACTED
            continue
        cleaned = _sanitize_value(value)
        if cleaned is not None:
            sanitized[name] = cleaned
    return sanitized


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text:
        return '""'
    if any(character in text for character in ' "='):
        return json.dumps(text, ensure_ascii=False)
    return text


def log_event(event: str, *, level: str | int = "info", **fields: Any) -> None:
    """Write one text line and one JSON line: ts LEVEL event key=value ..."""
    if not _configured:
        configure_logging()
    numeric_level = level if isinstance(level, int) else _LEVELS.get(level.lower(), logging.INFO)
    if not logging.getLogger(EVENT_LOGGER).isEnabledFor(numeric_level):
        return

    timestamp = datetime.now(GUATEMALA_TZ).isoformat(timespec="seconds")
    level_name = logging.getLevelName(numeric_level)
    sanitized = _sanitize_fields(fields)
    parts = [timestamp, level_name, event]
    parts.extend(f"{key}={_format_value(value)}" for key, value in sanitized.items())
    payload = {"ts": timestamp, "level": level_name, "event": event, **sanitized}

    # The event logger is not attached to the root logger, so uvicorn access lines
    # never reach the file; only SkinLedger events do.
    logging.getLogger(EVENT_LOGGER).log(
        numeric_level, " ".join(parts), extra={"event_json": payload}
    )


def mode_name(*, mock: bool) -> str:
    """The analysis mode recorded with every capture event."""
    return "mock" if mock else "real"
