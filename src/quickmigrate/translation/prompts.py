"""Prompt templates for the translation agent, kept separate from loop logic."""

from __future__ import annotations

import json

from ..models import ReportIR

SYSTEM_PROMPT = """You are an Amazon QuickSight migration expert. You convert \
normalized BI report metadata into a valid QuickSight dashboard definition \
JSON payload suitable for the boto3 quicksight.create_dashboard Definition \
parameter.

Rules:
- Output ONLY raw JSON. Do NOT wrap it in markdown code fences (no ```), and do \
not add any explanatory text before or after the JSON.
- The JSON MUST include a top-level "DataSetIdentifierDeclarations" array (one \
entry per datasource, each with an "Identifier" and a "DataSetArn") and a \
"Sheets" array (each sheet with a "Visuals" array).
- Every visual must map to a supported QuickSight visual type.
- If a required field is missing, choose a sensible default rather than omitting.
- When given a previous error, fix exactly that error and return the full \
corrected JSON.
"""


def build_seed_prompt(ir: ReportIR, datasets: list | None = None) -> str:
    """The initial user turn: the metadata to translate, plus the REAL datasets
    that exist in QuickSight so the model references genuine ARNs."""
    dataset_block = ""
    if datasets:
        lines = "\n".join(
            f'- Identifier: "{d.name}"  ARN: "{d.arn}"' for d in datasets
        )
        dataset_block = (
            "\n\nAVAILABLE QUICKSIGHT DATASETS (these already exist — you MUST use "
            "these exact ARNs and identifiers in DataSetIdentifierDeclarations; do "
            "NOT invent ARNs). Map every visual's data onto one of these:\n"
            + lines + "\n"
        )
    return (
        "Convert this normalized BI report metadata to a QuickSight dashboard "
        "definition JSON." + dataset_block +
        "\n\nMETADATA:\n" + json.dumps(ir.to_dict(), indent=2)
    )


def build_correction_prompt(error: str) -> str:
    """A follow-up user turn feeding a validation error back to the model."""
    return f"ERROR from validator: {error}. Return the full corrected JSON."
