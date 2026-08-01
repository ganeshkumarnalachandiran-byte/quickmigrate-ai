"""
The agentic translation loop.

Backend-agnostic. Drives the cycle:

    complete -> parse JSON -> validate -> if invalid, feed error back -> repeat

up to `max_retries`. The self-correction — feeding the validator's error back
into the conversation so the model fixes its own output — is what makes this an
agent rather than a one-shot call. Returns a TranslationResult carrying the full
error trail, which the flag report surfaces so a human (or a future auto-fallback)
knows exactly why a report failed.
"""

from __future__ import annotations

import json
import logging

from .backends.base import LLMBackend
from .prompts import build_seed_prompt, build_correction_prompt
from .validation import validate_payload
from ..errors import BackendError
from ..models import ReportIR, TranslationResult

log = logging.getLogger(__name__)


def translate(
    ir: ReportIR,
    backend: LLMBackend,
    max_retries: int = 3,
) -> TranslationResult:
    messages: list[dict[str, str]] = [
        {"role": "user", "content": build_seed_prompt(ir)}
    ]
    error_trail: list[str] = []

    for attempt in range(1, max_retries + 1):
        # --- get a candidate from the backend ---
        try:
            raw = backend.complete(messages, ir)
        except BackendError as exc:
            error_trail.append(f"backend_error: {exc}")
            log.warning("backend failed", extra={"file": ir.source_file, "attempt": attempt})
            return TranslationResult(
                ok=False, payload=None, attempts=attempt,
                error=str(exc), error_trail=error_trail,
            )

        # --- parse JSON ---
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            err = f"Invalid JSON: {exc}"
            error_trail.append(err)
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": build_correction_prompt(err)})
            continue

        # --- validate structure ---
        valid, verr = validate_payload(payload)
        if valid:
            log.debug(
                "translation succeeded",
                extra={"file": ir.source_file, "attempts": attempt},
            )
            return TranslationResult(
                ok=True, payload=payload, attempts=attempt,
                error=None, error_trail=error_trail,
            )

        # invalid -> feed the error back
        error_trail.append(verr or "unknown validation error")
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": build_correction_prompt(verr or "")})

    return TranslationResult(
        ok=False, payload=None, attempts=max_retries,
        error="Exhausted retries without a valid payload",
        error_trail=error_trail,
    )
