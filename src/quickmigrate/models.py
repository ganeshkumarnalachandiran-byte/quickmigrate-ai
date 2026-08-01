"""
Shared data models (the 'IR' — intermediate representation) and result types.

Keeping these in one module (rather than scattered across extractor/translator/
orchestrator) means every layer speaks the same vocabulary and there are no
circular imports between the pipeline stages.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


# Chart types the core engine claims it can translate. Anything outside this set
# raises the complexity score and pushes a report toward Transform.
SUPPORTED_MARKS: frozenset[str] = frozenset(
    {"bar", "line", "area", "text", "square", "circle"}
)


# --------------------------------------------------------------------------- #
# Intermediate representation
# --------------------------------------------------------------------------- #
@dataclass
class VizIR:
    name: str
    mark_type: str
    columns: list[str] = field(default_factory=list)
    raw_mark: str = ""  # what the source actually called it, pre-normalization


@dataclass
class ReportIR:
    source_file: str
    source_platform: str                      # tableau | powerbi | qlik
    datasources: list[str] = field(default_factory=list)
    visuals: list[VizIR] = field(default_factory=list)
    unknown_features: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Pipeline result types
# --------------------------------------------------------------------------- #
class Verdict(str, Enum):
    IN_SCOPE = "IN_SCOPE"
    FALLBACK = "FALLBACK"


@dataclass
class ComplexityResult:
    verdict: Verdict
    score: int
    reasons: list[str]


@dataclass
class TranslationResult:
    ok: bool
    payload: dict[str, Any] | None
    attempts: int
    error: str | None = None
    error_trail: list[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    ok: bool
    dashboard_id: str | None
    error: str | None = None


# --------------------------------------------------------------------------- #
# Report entries
# --------------------------------------------------------------------------- #
@dataclass
class MigratedEntry:
    source_file: str
    platform: str
    dashboard_id: str
    attempts: int
    visuals: int


@dataclass
class FlaggedEntry:
    source_file: str
    platform: str
    stage: str                                # extract | score | translate | execute
    reasons: list[str]
    error_trail: list[str] = field(default_factory=list)
    transform_prereq: str = ""
    # The payload a future auto-fallback would hand to a Transform API.
    fallback_hint: dict[str, Any] = field(default_factory=dict)
