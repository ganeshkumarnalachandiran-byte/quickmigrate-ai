"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from quickmigrate.config import Settings, Mode, TriageThresholds

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def mock_settings() -> Settings:
    """Deterministic offline settings for unit tests."""
    return Settings(mode=Mode.MOCK, max_retries=3, thresholds=TriageThresholds())
