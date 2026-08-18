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
import re

from .backends.base import LLMBackend
from .prompts import build_seed_prompt, build_correction_prompt
from .validation import validate_payload
from ..errors import BackendError
from ..models import ReportIR, TranslationResult

log = logging.getLogger(__name__)

def _extract_json(raw: str) -> str:
    """
    Pull a JSON object out of the model's raw text response.

    Models often wrap JSON in markdown fences (```json ... ```) or add a line
    of preamble. We strip fences if present, otherwise fall back to grabbing
    everything from the first { to the last } so stray text around the JSON
    doesn't break parsing. If nothing JSON-looking is found, return the text
    unchanged so the parse error stays honest.
    """
    text = raw.strip()

    # Case 1: fenced code block, with or without a language tag.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        return fence.group(1).strip()

    # Case 2: no fence — take from first { to last } inclusive.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]

    # Case 3: nothing JSON-looking; return as-is.
    return text


def translate(
    ir: ReportIR,
    backend: LLMBackend,
    max_retries: int = 3,
    datasets: list | None = None,
) -> TranslationResult:
    messages: list[dict[str, str]] = [
        {"role": "user", "content": build_seed_prompt(ir, datasets)}
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
            payload = json.loads(_extract_json(raw))
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
