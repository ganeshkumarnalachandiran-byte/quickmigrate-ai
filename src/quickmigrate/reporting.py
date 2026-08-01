"""
Reporting.

Assembles the MigrationReport (migrated + flagged buckets) and renders it two
ways: a machine-readable dict (written to JSON) and a human summary (printed to
stdout). Separated from the orchestrator so output format can change without
touching pipeline logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from .models import MigratedEntry, FlaggedEntry


@dataclass
class MigrationReport:
    migrated: list[MigratedEntry] = field(default_factory=list)
    flagged: list[FlaggedEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "total": len(self.migrated) + len(self.flagged),
                "migrated": len(self.migrated),
                "flagged": len(self.flagged),
            },
            "migrated": [asdict(m) for m in self.migrated],
            "flagged": [asdict(f) for f in self.flagged],
        }


def render_human_summary(report: MigrationReport) -> str:
    d = report.to_dict()
    s = d["summary"]
    lines = [
        "",
        "=" * 60,
        "  QuickMigrate-AI  —  Migration Report",
        "=" * 60,
        f"  Total reports : {s['total']}",
        f"  Migrated      : {s['migrated']}",
        f"  Flagged       : {s['flagged']}  (candidates for AWS Transform)",
        "=" * 60,
    ]

    if d["migrated"]:
        lines.append("")
        lines.append("  MIGRATED")
        for m in d["migrated"]:
            lines.append(
                f"    + {Path(m['source_file']).name}  -> {m['dashboard_id']}  "
                f"({m['visuals']} visuals, {m['attempts']} attempt(s))"
            )

    if d["flagged"]:
        lines.append("")
        lines.append("  FLAGGED FOR TRANSFORM")
        for f in d["flagged"]:
            lines.append(
                f"    - {Path(f['source_file']).name}  [{f['platform']}]  "
                f"stopped at: {f['stage']}"
            )
            for r in f["reasons"][:4]:
                lines.append(f"        - {r}")
            if len(f["reasons"]) > 4:
                lines.append(f"        - (+{len(f['reasons']) - 4} more)")
            if f["transform_prereq"]:
                lines.append(f"        prereq: {f['transform_prereq']}")

    lines.append("")
    return "\n".join(lines)
