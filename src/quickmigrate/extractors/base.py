"""Extractor interface. Each source platform implements one."""

from __future__ import annotations

import abc
from pathlib import Path

from ..models import ReportIR


class Extractor(abc.ABC):
    """Parses a source BI file into a normalized ReportIR."""

    #: File suffixes this extractor handles, e.g. (".twb",)
    suffixes: tuple[str, ...] = ()

    #: Platform label written into the IR.
    platform: str = "unknown"

    @abc.abstractmethod
    def extract(self, path: Path) -> ReportIR:
        """Parse `path` and return a ReportIR. Raise ExtractionError on failure."""
        raise NotImplementedError
