"""Reporting + orchestrator (mock-mode) unit tests."""

from __future__ import annotations

from quickmigrate.orchestrator import Orchestrator
from quickmigrate.reporting import render_human_summary
from pathlib import Path


def test_full_batch_buckets_correctly(fixtures_dir, mock_settings):
    files = sorted(fixtures_dir.glob("*.twb")) + sorted(fixtures_dir.glob("*.pbix"))
    report = Orchestrator(mock_settings).run_batch(files)
    d = report.to_dict()

    assert d["summary"]["total"] == 3
    assert d["summary"]["migrated"] == 1
    assert d["summary"]["flagged"] == 2

    migrated_names = {Path(e["source_file"]).name for e in d["migrated"]}
    assert "sales_simple.twb" in migrated_names


def test_flagged_entries_carry_fallback_hint(fixtures_dir, mock_settings):
    report = Orchestrator(mock_settings).run_batch(
        [fixtures_dir / "exec_dashboard_complex.twb"]
    )
    flagged = report.to_dict()["flagged"]
    assert len(flagged) == 1
    entry = flagged[0]
    assert entry["stage"] == "score"
    assert entry["fallback_hint"], "fallback_hint must be populated for the future API"
    assert entry["transform_prereq"]


def test_pbix_flagged_at_extract(fixtures_dir, mock_settings):
    report = Orchestrator(mock_settings).run_batch([fixtures_dir / "finance.pbix"])
    entry = report.to_dict()["flagged"][0]
    assert entry["stage"] == "extract"
    assert entry["platform"] == "powerbi"


def test_human_summary_renders(fixtures_dir, mock_settings):
    files = sorted(fixtures_dir.glob("*.twb"))
    report = Orchestrator(mock_settings).run_batch(files)
    text = render_human_summary(report)
    assert "Migration Report" in text
    assert "MIGRATED" in text
