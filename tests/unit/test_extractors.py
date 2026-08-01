"""Extractor unit tests."""

from __future__ import annotations

import pytest

from quickmigrate.extractors import extract, get_extractor, platform_for_suffix
from quickmigrate.errors import UnsupportedSourceError, ExtractionError


def test_tableau_extraction(fixtures_dir):
    ir = extract(fixtures_dir / "sales_simple.twb")
    assert ir.source_platform == "tableau"
    assert len(ir.visuals) == 2
    names = {v.name for v in ir.visuals}
    assert names == {"Revenue by Region", "Revenue Trend"}
    marks = {v.mark_type for v in ir.visuals}
    assert marks == {"bar", "line"}


def test_tableau_complex_flags_features(fixtures_dir):
    ir = extract(fixtures_dir / "exec_dashboard_complex.twb")
    # calc fields, params, actions should all be recorded
    joined = " ".join(ir.unknown_features)
    assert "calculated_fields" in joined
    assert "parameters:present" in joined
    assert "actions" in joined
    # unsupported marks preserved
    marks = {v.mark_type for v in ir.visuals}
    assert "map" in marks and "pie" in marks and "gantt" in marks


def test_powerbi_routes_to_fallback(fixtures_dir):
    with pytest.raises(UnsupportedSourceError):
        extract(fixtures_dir / "finance.pbix")


def test_unknown_suffix_raises():
    from pathlib import Path
    with pytest.raises(UnsupportedSourceError):
        get_extractor(Path("something.xyz"))


def test_platform_for_suffix():
    assert platform_for_suffix(".twb") == "tableau"
    assert platform_for_suffix(".pbix") == "powerbi"
    assert platform_for_suffix(".qvf") == "qlik"
    assert platform_for_suffix(".xyz") == "unknown"


def test_malformed_xml_raises(tmp_path):
    bad = tmp_path / "broken.twb"
    bad.write_text("<workbook><unclosed>")
    with pytest.raises(ExtractionError):
        extract(bad)
