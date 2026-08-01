"""
Complexity scorer — the triage brain.

Given a ReportIR and the configured thresholds, produces IN_SCOPE or FALLBACK.
Scoring happens BEFORE any translation attempt so we never spend model tokens on
a report we already know is out of scope. All policy comes from
TriageThresholds (config), so tuning what the engine 'claims' it can do is a
config change, not a code change.
"""

from __future__ import annotations

import logging

from ..config import TriageThresholds
from ..models import ComplexityResult, ReportIR, Verdict, SUPPORTED_MARKS

log = logging.getLogger(__name__)


def score_report(ir: ReportIR, thresholds: TriageThresholds) -> ComplexityResult:
    reasons: list[str] = []
    score = 0

    # 1. Unsupported chart types — strongest signal.
    for viz in ir.visuals:
        if viz.mark_type not in SUPPORTED_MARKS:
            score += 5
            reasons.append(
                f"Unsupported chart type '{viz.mark_type}' in visual '{viz.name}'"
            )

    # 2. Too many visuals.
    if len(ir.visuals) > thresholds.max_visuals:
        score += 3
        reasons.append(
            f"{len(ir.visuals)} visuals exceeds limit of {thresholds.max_visuals}"
        )

    # 3. Multi-datasource.
    if len(ir.datasources) > thresholds.max_datasources:
        score += 3
        reasons.append(
            f"{len(ir.datasources)} datasources exceeds limit "
            f"of {thresholds.max_datasources}"
        )

    # 4. Wide visuals.
    for viz in ir.visuals:
        if len(viz.columns) > thresholds.max_columns_per_viz:
            score += 2
            reasons.append(
                f"Visual '{viz.name}' uses {len(viz.columns)} columns "
                f"(> {thresholds.max_columns_per_viz})"
            )

    # 5. Advanced features the extractor flagged.
    for feature in ir.unknown_features:
        score += 2
        reasons.append(f"Advanced feature detected: {feature}")

    # 6. Empty extraction is itself suspicious.
    if not ir.visuals:
        score += 5
        reasons.append("No visuals extracted — likely an unsupported layout")

    verdict = Verdict.FALLBACK if score >= thresholds.fallback_score else Verdict.IN_SCOPE
    log.debug(
        "scored report",
        extra={"file": ir.source_file, "score": score, "verdict": verdict.value},
    )
    return ComplexityResult(verdict=verdict, score=score, reasons=reasons)
