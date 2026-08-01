"""
Qlik .qvf extractor.

Not implemented in the MVP. Qlik Sense apps (.qvf) are proprietary binary
containers; extraction typically requires the Qlik Engine API rather than static
file parsing. Raises UnsupportedSourceError so .qvf routes to Transform.

Note: as of build time, verify whether the AWS Transform BI agents support Qlik
at all — they were announced for Tableau and Power BI. Qlik may need a different
migration path entirely.
"""

from __future__ import annotations

from pathlib import Path

from .base import Extractor
from ..errors import UnsupportedSourceError
from ..models import ReportIR


class QlikExtractor(Extractor):
    suffixes = (".qvf",)
    platform = "qlik"

    def extract(self, path: Path) -> ReportIR:
        raise UnsupportedSourceError(
            "Qlik .qvf parsing is not implemented in the MVP core engine. "
            "Route to Transform fallback (verify Qlik support first)."
        )
