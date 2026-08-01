"""
Transform fallback.

Builds the FlaggedEntry payload for reports the core engine can't handle. The
`fallback_hint` it assembles is the exact metadata a future version would POST to
an AWS Transform API to automate the hand-off — the structure exists today even
though the invocation is manual.

Note: AWS Transform's BI agents (Wavicle/EZConvertBI) are currently a
self-service, conversational capability inside AWS Transform, not a documented
public headless API. Verify current API availability with your AWS account team
before building `submit_to_transform`.
"""

from __future__ import annotations

from typing import Any

from ..models import FlaggedEntry, ReportIR

# What Transform needs to pick up a flagged report, by platform.
TRANSFORM_PREREQS: dict[str, str] = {
    "tableau": "Enable Tableau Metadata API and generate a Personal Access Token (PAT).",
    "powerbi": "Configure workspace access + service principal authentication.",
    "qlik": "Not confirmed supported by the BI migration agents; verify with AWS.",
    "unknown": "Confirm source access requirements with your AWS account team.",
}


def prereq_for(platform: str) -> str:
    return TRANSFORM_PREREQS.get(platform, TRANSFORM_PREREQS["unknown"])


def build_flag(
    source_file: str,
    platform: str,
    stage: str,
    reasons: list[str],
    error_trail: list[str] | None = None,
    fallback_hint: dict[str, Any] | None = None,
) -> FlaggedEntry:
    return FlaggedEntry(
        source_file=source_file,
        platform=platform,
        stage=stage,
        reasons=reasons,
        error_trail=error_trail or [],
        transform_prereq=prereq_for(platform),
        fallback_hint=fallback_hint or {"source_file": source_file, "platform": platform},
    )


def hint_from_ir(ir: ReportIR) -> dict[str, Any]:
    """The metadata payload a Transform API call would carry."""
    return ir.to_dict()


def submit_to_transform(flagged: FlaggedEntry) -> None:
    """
    Placeholder for the future automated hand-off.

    When/if a headless Transform BI API exists, this method would POST
    `flagged.fallback_hint` (plus credentials) to launch a conversion job and
    return a job id. Deliberately unimplemented so the boundary is explicit.
    """
    raise NotImplementedError(
        "Automated Transform submission is not yet available. "
        "Run flagged reports through AWS Transform manually for now."
    )
