"""
PowerBI .pbix extractor.

Not implemented in the MVP. A .pbix is a ZIP containing a Layout JSON plus a
compiled data model (an Analysis Services / VertiPaq blob). Reading the layout
is feasible; reading the model reliably is not a weekend job. Until then this
raises UnsupportedSourceError so the orchestrator routes .pbix straight to the
Transform fallback bucket instead of failing mid-pipeline.

Implementation sketch for later:
  - unzip the .pbix
  - parse `Report/Layout` (UTF-16 JSON) for visuals and their field bindings
  - the data model itself is best left to Transform / a dedicated library
"""

from __future__ import annotations

from pathlib import Path

from .base import Extractor
from ..errors import UnsupportedSourceError
from ..models import ReportIR


class PowerBIExtractor(Extractor):
    suffixes = (".pbix",)
    platform = "powerbi"

    def extract(self, path: Path) -> ReportIR:
        raise UnsupportedSourceError(
            "PowerBI .pbix parsing is not implemented in the MVP core engine. "
            "Route to Transform fallback."
        )
