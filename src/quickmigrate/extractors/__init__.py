"""
Extractor registry.

Maps file suffixes to Extractor instances. This is the single place to register
a new source platform — add the extractor module, then one line here. The
orchestrator never imports concrete extractors; it calls `get_extractor(path)`.
"""

from __future__ import annotations

from pathlib import Path

from .base import Extractor
from .tableau import TableauExtractor
from .powerbi import PowerBIExtractor
from .qlik import QlikExtractor
from ..errors import UnsupportedSourceError
from ..models import ReportIR

# Instantiate once; extractors are stateless.
_EXTRACTORS: list[Extractor] = [
    TableauExtractor(),
    PowerBIExtractor(),
    QlikExtractor(),
]

# Build suffix -> extractor lookup.
_BY_SUFFIX: dict[str, Extractor] = {
    suffix: ex for ex in _EXTRACTORS for suffix in ex.suffixes
}

# Suffixes the CLI should even bother scanning for in a directory.
KNOWN_SUFFIXES: tuple[str, ...] = tuple(_BY_SUFFIX.keys())


def platform_for_suffix(suffix: str) -> str:
    ex = _BY_SUFFIX.get(suffix.lower())
    return ex.platform if ex else "unknown"


def get_extractor(path: Path) -> Extractor:
    ex = _BY_SUFFIX.get(path.suffix.lower())
    if ex is None:
        raise UnsupportedSourceError(
            f"No extractor for '{path.suffix}' files. Route to Transform fallback."
        )
    return ex


def extract(path: Path) -> ReportIR:
    """Convenience: resolve the extractor and run it."""
    return get_extractor(path).extract(path)


__all__ = [
    "Extractor",
    "get_extractor",
    "extract",
    "platform_for_suffix",
    "KNOWN_SUFFIXES",
]
