"""
Logging setup.

Two modes:
  - plain (default): human-readable, for local runs and demos.
  - json: one JSON object per line, for prod log aggregation (CloudWatch, etc.).

Call configure_logging() once at startup (the CLI does this). Everywhere else,
use `logging.getLogger(__name__)` as normal.
"""

from __future__ import annotations

import json
import logging
import sys


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Attach any extra structured fields passed via logger.info(..., extra={...})
        for key, val in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = val
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


def configure_logging(level: str = "INFO", as_json: bool = False) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stderr)
    if as_json:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(levelname)-7s %(name)s: %(message)s")
        )
    root.addHandler(handler)
