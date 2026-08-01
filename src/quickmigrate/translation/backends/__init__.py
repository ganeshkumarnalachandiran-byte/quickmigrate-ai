"""Backend selection based on Settings.mode."""

from __future__ import annotations

from .base import LLMBackend
from .bedrock import BedrockBackend
from .mock import MockBackend
from ...config import Mode, Settings


def get_backend(settings: Settings) -> LLMBackend:
    if settings.mode is Mode.BEDROCK:
        return BedrockBackend(settings)
    return MockBackend()


__all__ = ["LLMBackend", "BedrockBackend", "MockBackend", "get_backend"]
