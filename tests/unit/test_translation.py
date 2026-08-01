"""Translation agent unit tests — retry loop and backend behavior."""

from __future__ import annotations

import json

from quickmigrate.extractors import extract
from quickmigrate.models import ReportIR, VizIR
from quickmigrate.translation import translate
from quickmigrate.translation.backends.mock import MockBackend
from quickmigrate.translation.backends.base import LLMBackend
from quickmigrate.translation.validation import validate_payload
from quickmigrate.errors import BackendError


def test_retry_loop_self_corrects(fixtures_dir):
    """Mock omits a required field on attempt 1, fixes it on attempt 2."""
    ir = extract(fixtures_dir / "sales_simple.twb")
    tr = translate(ir, MockBackend(), max_retries=3)
    assert tr.ok
    assert tr.attempts == 2, f"expected self-correction on 2nd attempt, got {tr.attempts}"
    assert tr.error_trail, "first-attempt error should be recorded"
    ok, err = validate_payload(tr.payload)
    assert ok, err


def test_backend_error_is_flagged_not_raised():
    class BoomBackend(LLMBackend):
        def complete(self, messages, ir):
            raise BackendError("simulated throttle")

    ir = ReportIR(source_file="x.twb", source_platform="tableau",
                  visuals=[VizIR(name="Bar", mark_type="bar")])
    tr = translate(ir, BoomBackend(), max_retries=3)
    assert not tr.ok
    assert "simulated throttle" in (tr.error or "")


def test_invalid_json_triggers_retry():
    """A backend that returns junk once, then valid JSON, should recover."""
    class FlakyBackend(LLMBackend):
        def __init__(self):
            self.calls = 0

        def complete(self, messages, ir):
            self.calls += 1
            if self.calls == 1:
                return "not json at all"
            return json.dumps({
                "DataSetIdentifierDeclarations": [],
                "Sheets": [{"Visuals": []}],
            })

    ir = ReportIR(source_file="x.twb", source_platform="tableau",
                  visuals=[VizIR(name="Bar", mark_type="bar")])
    tr = translate(ir, FlakyBackend(), max_retries=3)
    assert tr.ok
    assert tr.attempts == 2


def test_exhausts_retries_when_never_valid():
    class NeverValidBackend(LLMBackend):
        def complete(self, messages, ir):
            return json.dumps({"nope": True})

    ir = ReportIR(source_file="x.twb", source_platform="tableau",
                  visuals=[VizIR(name="Bar", mark_type="bar")])
    tr = translate(ir, NeverValidBackend(), max_retries=3)
    assert not tr.ok
    assert tr.attempts == 3
    assert len(tr.error_trail) == 3
