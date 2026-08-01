"""
Typed exception hierarchy.

A broad `except Exception` throws away the one thing the flag report needs: WHY
a migration failed. These types let the orchestrator distinguish, for example,
"the source file was malformed" (user's problem) from "Bedrock threw" (transient,
retryable) from "genuinely out of scope" (route to Transform) — and record the
right stage and guidance for each.

The `stage` attribute maps onto the pipeline steps so the report can say exactly
where a report fell out.
"""

from __future__ import annotations


class QuickMigrateError(Exception):
    """Base class for all QuickMigrate errors."""
    stage: str = "unknown"


class ExtractionError(QuickMigrateError):
    """Source file could not be parsed (malformed, unsupported layout)."""
    stage = "extract"


class UnsupportedSourceError(ExtractionError):
    """No extractor exists for this file type. -> Transform fallback."""
    stage = "extract"


class TranslationError(QuickMigrateError):
    """The agent could not produce a valid payload within the retry budget."""
    stage = "translate"


class BackendError(QuickMigrateError):
    """The LLM backend itself failed (network, auth, throttle)."""
    stage = "translate"


class ExecutionError(QuickMigrateError):
    """QuickSight rejected the create_dashboard call."""
    stage = "execute"


class ConfigError(QuickMigrateError):
    """Invalid or missing configuration."""
    stage = "config"
