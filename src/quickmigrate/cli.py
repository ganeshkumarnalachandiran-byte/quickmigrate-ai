"""
QuickMigrate-AI CLI.

    quickmigrate --input samples/ --output output/report.json
    quickmigrate --input samples/sales_simple.twb

Config is environment-driven (see .env.example). QM_MODE=mock (default) runs
fully offline; QM_MODE=bedrock uses real Bedrock + QuickSight.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Settings
from .errors import ConfigError
from .extractors import KNOWN_SUFFIXES
from .logging import configure_logging
from .orchestrator import Orchestrator
from .reporting import render_human_summary


def _gather_inputs(input_path: Path) -> list[Path]:
    if input_path.is_dir():
        return sorted(
            p for p in input_path.iterdir()
            if p.suffix.lower() in KNOWN_SUFFIXES
        )
    return [input_path]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="quickmigrate",
        description=(
            "Migrate BI reports to Amazon QuickSight; flag the ones the core "
            "engine can't handle for AWS Transform."
        ),
    )
    p.add_argument("--input", "-i", required=True, help="A source file or directory.")
    p.add_argument("--output", "-o", default=None, help="Path for the JSON report.")
    p.add_argument(
        "--max-retries", type=int, default=None,
        help="Override agent self-correction attempts (default from config).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    settings = Settings.from_env()
    if args.max_retries is not None:
        # argparse override wins over env.
        object.__setattr__(settings, "max_retries", args.max_retries)

    configure_logging(level=settings.log_level, as_json=settings.log_json)

    try:
        settings.require_bedrock_config()
    except ValueError as exc:
        raise SystemExit(f"config error: {exc}") from exc

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"error: input path not found: {input_path}", file=sys.stderr)
        return 2

    files = _gather_inputs(input_path)
    if not files:
        print(
            f"error: no {'/'.join(KNOWN_SUFFIXES)} files found under {input_path}",
            file=sys.stderr,
        )
        return 2

    report = Orchestrator(settings).run_batch(files)
    report_dict = report.to_dict()

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report_dict, indent=2))
        print(f"report written to {out}")

    print(render_human_summary(report))

    return 0 if not report_dict["flagged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
