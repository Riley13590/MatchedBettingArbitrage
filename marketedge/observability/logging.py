"""Structured JSON logging (spec section 23.1).

Every log line is a single JSON object. Never pass secrets (passwords, API
keys, session tokens) as fields — spec section 23.1 explicitly forbids it.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from typing import Any

import orjson

_REDACT_KEYS = {"password", "app_key", "session_token", "api_key", "secret", "cert", "key_path"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", record.name),
            "message": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if extra:
            for k, v in extra.items():
                payload[k] = "***REDACTED***" if _looks_secret(k) else v
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return orjson.dumps(payload).decode()


def _looks_secret(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _REDACT_KEYS)


def configure_logging(level: str = "INFO", service: str = "marketedge") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    old_factory = logging.getLogRecordFactory()

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = old_factory(*args, **kwargs)
        record.service = service
        return record

    logging.setLogRecordFactory(factory)


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    logger.log(level, event, extra={"fields": {"event": event, **fields}})
