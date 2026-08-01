"""Prompt templates for the translation agent, kept separate from loop logic."""

from __future__ import annotations

import json

from ..models import ReportIR

SYSTEM_PROMPT = """You are an Amazon QuickSight migration expert. You convert \
normalized BI report metadata into a valid QuickSight dashboard definition JSON \
payload suitable for the boto3 quicksight.create_dashboard Definition parameter.

Rules:
- Output ONLY valid JSON. No prose, no markdown fences.
- Every visual must map to a supported QuickSight visual type.
- If a required field is missing, choose a sensible default rather than omitting.
- When given a previous error, fix exactly that error and return the full \
corrected JSON.
"""


def build_seed_prompt(ir: ReportIR) -> str:
    """The initial user turn: the metadata to translate."""
    return (
        "Convert this normalized BI report metadata to a QuickSight dashboard "
        "definition JSON.\n\nMETADATA:\n" + json.dumps(ir.to_dict(), indent=2)
    )


def build_correction_prompt(error: str) -> str:
    """A follow-up user turn feeding a validation error back to the model."""
    return f"ERROR from validator: {error}. Return the full corrected JSON."
