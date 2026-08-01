"""Complexity scorer unit tests."""

from __future__ import annotations

from quickmigrate.config import TriageThresholds
from quickmigrate.extractors import extract
from quickmigrate.models import ReportIR, VizIR, Verdict
from quickmigrate.triage import score_report


def test_simple_is_in_scope(fixtures_dir):
    ir = extract(fixtures_dir / "sales_simple.twb")
    result = score_report(ir, TriageThresholds())
    assert result.verdict == Verdict.IN_SCOPE
    assert result.score < TriageThresholds().fallback_score


def test_complex_is_fallback(fixtures_dir):
    ir = extract(fixtures_dir / "exec_dashboard_complex.twb")
    result = score_report(ir, TriageThresholds())
    assert result.verdict == Verdict.FALLBACK
    assert result.reasons


def test_unsupported_chart_alone_triggers_fallback():
    ir = ReportIR(
        source_file="x.twb", source_platform="tableau",
        datasources=["ds"], visuals=[VizIR(name="Pie", mark_type="pie")],
    )
    assert score_report(ir, TriageThresholds()).verdict == Verdict.FALLBACK


def test_empty_visuals_triggers_fallback():
    ir = ReportIR(source_file="x.twb", source_platform="tableau")
    assert score_report(ir, TriageThresholds()).verdict == Verdict.FALLBACK


def test_thresholds_are_tunable():
    """
    The fallback threshold itself is tunable. A single mild signal (3
    datasources over a limit of 2 => +3) is intentionally BELOW the default
    fallback score of 5, so it stays in scope. Lowering the fallback score to 3
    makes the same report tip to fallback — proving the policy is config-driven.
    """
    ir = ReportIR(
        source_file="x.twb", source_platform="tableau", datasources=["a", "b", "c"],
        visuals=[VizIR(name="Bar", mark_type="bar")],
    )
    lenient = TriageThresholds(max_datasources=2, fallback_score=5)   # default
    strict = TriageThresholds(max_datasources=2, fallback_score=3)    # stricter
    assert score_report(ir, lenient).verdict == Verdict.IN_SCOPE
    assert score_report(ir, strict).verdict == Verdict.FALLBACK
