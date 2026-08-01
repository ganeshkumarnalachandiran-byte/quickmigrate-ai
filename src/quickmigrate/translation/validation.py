"""
Payload validation.

A lightweight structural check that approximates the QuickSight create_dashboard
contract. In `bedrock` mode the REAL validator is the boto3 call in
execution/quicksight.py — its rejections are what the agent's retry loop should
ultimately consume. This structural check lets the loop be exercised offline and
catches obvious errors before we spend an API call.
"""

from __future__ import annotations

from typing import Any


def validate_payload(payload: Any) -> tuple[bool, str | None]:
    if not isinstance(payload, dict):
        return False, "Payload is not a JSON object"
    if "DataSetIdentifierDeclarations" not in payload:
        return False, "Missing required field 'DataSetIdentifierDeclarations'"
    sheets = payload.get("Sheets")
    if not sheets or not isinstance(sheets, list):
        return False, "Missing or empty 'Sheets' array"
    for i, sheet in enumerate(sheets):
        if "Visuals" not in sheet:
            return False, f"Sheet {i} missing 'Visuals' array"
    return True, None
