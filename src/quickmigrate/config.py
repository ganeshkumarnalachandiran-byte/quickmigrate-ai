"""
Centralized, typed configuration.

Everything tunable lives here and is loaded once from the environment (or a
.env file, if python-dotenv is installed). No module reaches into os.environ
directly — they take a Settings object. That makes the app testable (pass a
Settings in a test) and makes every knob discoverable in one place.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


class Mode(str, Enum):
    """Execution backend selector."""
    MOCK = "mock"        # fully offline, deterministic, zero cost
    BEDROCK = "bedrock"  # real Amazon Bedrock + QuickSight


def _load_dotenv_if_present() -> None:
    """Best-effort .env loading. Never a hard dependency."""
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except Exception:  # noqa: BLE001
        pass


@dataclass(frozen=True)
class TriageThresholds:
    """The complete triage policy — what the core engine 'claims' it can do."""
    max_visuals: int = 8
    max_datasources: int = 2
    max_columns_per_viz: int = 12
    fallback_score: int = 5  # score >= this => route to Transform


@dataclass(frozen=True)
class Settings:
    mode: Mode = Mode.MOCK

    # Bedrock
    bedrock_model_id: str = "anthropic.claude-sonnet-4-6"  # VERIFY before prod
    bedrock_max_tokens: int = 4096
    aws_region: str | None = None

    # QuickSight
    aws_account_id: str | None = None

    # Agent behavior
    max_retries: int = 3

    # Triage
    thresholds: TriageThresholds = field(default_factory=TriageThresholds)

    # Logging
    log_level: str = "INFO"
    log_json: bool = False  # True => structured JSON logs (for prod aggregation)

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv_if_present()

        def _int(name: str, default: int) -> int:
            raw = os.environ.get(name)
            return int(raw) if raw and raw.isdigit() else default

        def _bool(name: str, default: bool) -> bool:
            raw = os.environ.get(name)
            if raw is None:
                return default
            return raw.strip().lower() in ("1", "true", "yes", "on")

        mode_raw = os.environ.get("QM_MODE", Mode.MOCK.value).lower()
        try:
            mode = Mode(mode_raw)
        except ValueError:
            mode = Mode.MOCK

        return cls(
            mode=mode,
            bedrock_model_id=os.environ.get(
                "QM_BEDROCK_MODEL", cls.bedrock_model_id
            ),
            bedrock_max_tokens=_int("QM_BEDROCK_MAX_TOKENS", cls.bedrock_max_tokens),
            aws_region=os.environ.get("QM_AWS_REGION") or os.environ.get("AWS_REGION"),
            aws_account_id=os.environ.get("QM_AWS_ACCOUNT_ID"),
            max_retries=_int("QM_MAX_RETRIES", cls.max_retries),
            thresholds=TriageThresholds(
                max_visuals=_int("QM_MAX_VISUALS", TriageThresholds.max_visuals),
                max_datasources=_int(
                    "QM_MAX_DATASOURCES", TriageThresholds.max_datasources
                ),
                max_columns_per_viz=_int(
                    "QM_MAX_COLUMNS_PER_VIZ", TriageThresholds.max_columns_per_viz
                ),
                fallback_score=_int(
                    "QM_FALLBACK_SCORE", TriageThresholds.fallback_score
                ),
            ),
            log_level=os.environ.get("QM_LOG_LEVEL", cls.log_level).upper(),
            log_json=_bool("QM_LOG_JSON", cls.log_json),
        )

    def require_bedrock_config(self) -> None:
        """Fail fast with a clear message if bedrock mode is missing config."""
        if self.mode is not Mode.BEDROCK:
            return
        missing = []
        if not self.aws_account_id:
            missing.append("QM_AWS_ACCOUNT_ID")
        if missing:
            raise ValueError(
                "bedrock mode requires: " + ", ".join(missing)
                + ". Set them in the environment or .env file."
            )
