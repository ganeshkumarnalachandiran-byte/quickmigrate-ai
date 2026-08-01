"""
Orchestrator: wires the pipeline for a batch of files.

Per file:
    extract -> score -> (FALLBACK? flag) -> translate -> (fail? flag) ->
    execute -> (fail? flag) -> migrated

Dependencies (settings, backend, executor) are constructed once and passed in,
so the orchestrator is testable in isolation and the whole run shares one config.
Typed errors from each stage are caught here and turned into flagged entries with
the right stage label and Transform prerequisite.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .config import Settings
from .errors import ExtractionError
from .execution import QuickSightExecutor
from .extractors import extract as extract_source, platform_for_suffix
from .fallback import build_flag, hint_from_ir
from .models import MigratedEntry, Verdict
from .reporting import MigrationReport
from .translation import get_backend, translate
from .triage import score_report

log = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._backend = get_backend(settings)
        self._executor = QuickSightExecutor(settings)

    def migrate_file(self, path: Path):
        """Returns ('migrated', MigratedEntry) or ('flagged', FlaggedEntry)."""
        platform = platform_for_suffix(path.suffix)

        # --- extract ---
        try:
            ir = extract_source(path)
            platform = ir.source_platform
        except ExtractionError as exc:
            return "flagged", build_flag(
                str(path), platform, exc.stage, [str(exc)],
                fallback_hint={"source_file": str(path), "platform": platform},
            )
        except Exception as exc:  # noqa: BLE001 — unexpected parse failure
            log.exception("unexpected extraction failure", extra={"file": str(path)})
            return "flagged", build_flag(
                str(path), platform, "extract", [f"Extraction failed: {exc}"],
                fallback_hint={"source_file": str(path), "platform": platform},
            )

        # --- score ---
        result = score_report(ir, self._settings.thresholds)
        if result.verdict == Verdict.FALLBACK:
            return "flagged", build_flag(
                str(path), platform, "score", result.reasons,
                fallback_hint=hint_from_ir(ir),
            )

        # --- translate (agentic loop) ---
        tr = translate(ir, self._backend, max_retries=self._settings.max_retries)
        if not tr.ok:
            return "flagged", build_flag(
                str(path), platform, "translate", [tr.error or "translation failed"],
                error_trail=tr.error_trail, fallback_hint=hint_from_ir(ir),
            )

        # --- execute ---
        ex = self._executor.create_dashboard(tr.payload or {}, dashboard_name=path.stem)
        if not ex.ok:
            return "flagged", build_flag(
                str(path), platform, "execute",
                [f"QuickSight rejected the dashboard: {ex.error}"],
                error_trail=tr.error_trail + [ex.error or ""],
                fallback_hint=hint_from_ir(ir),
            )

        return "migrated", MigratedEntry(
            source_file=str(path),
            platform=platform,
            dashboard_id=ex.dashboard_id or "",
            attempts=tr.attempts,
            visuals=len(ir.visuals),
        )

    def run_batch(self, paths: list[Path]) -> MigrationReport:
        report = MigrationReport()
        for p in paths:
            kind, entry = self.migrate_file(p)
            if kind == "migrated":
                report.migrated.append(entry)
                log.info("migrated", extra={"file": str(p)})
            else:
                report.flagged.append(entry)
                log.info("flagged", extra={"file": str(p), "stage": entry.stage})
        return report
