"""Tableau .twb (workbook XML) extractor."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

from .base import Extractor
from ..errors import ExtractionError
from ..models import ReportIR, VizIR

log = logging.getLogger(__name__)


_MARK_MAP = {
    "automatic": "bar",   # Tableau default; assume bar for MVP
    "bar": "bar",
    "line": "line",
    "area": "area",
    "text": "text",
    "square": "square",
    "circle": "circle",
    "shape": "circle",
    # deliberately NOT in SUPPORTED_MARKS — these should push to fallback:
    "gantt": "gantt",
    "polygon": "polygon",
    "pie": "pie",
    "map": "map",
}


def _normalize_mark(raw: str) -> str:
    return _MARK_MAP.get((raw or "").strip().lower(), (raw or "unknown").lower())


class TableauExtractor(Extractor):
    suffixes = (".twb",)
    platform = "tableau"

    def extract(self, path: Path) -> ReportIR:
        try:
            tree = ET.parse(path)
        except ET.ParseError as exc:
            raise ExtractionError(f"Malformed Tableau XML: {exc}") from exc

        root = tree.getroot()
        ir = ReportIR(source_file=str(path), source_platform=self.platform)

        self._extract_datasources(root, ir)
        self._extract_visuals(root, ir)
        self._extract_advanced_features(root, ir)

        log.debug(
            "extracted tableau workbook",
            extra={
                "file": str(path),
                "visuals": len(ir.visuals),
                "datasources": len(ir.datasources),
            },
        )
        return ir

    @staticmethod
    def _extract_datasources(root: ET.Element, ir: ReportIR) -> None:
        for ds in root.iter("datasource"):
            caption = ds.get("caption") or ds.get("name")
            if caption and caption.lower() != "parameters" and caption not in ir.datasources:
                ir.datasources.append(caption)

    @staticmethod
    def _extract_visuals(root: ET.Element, ir: ReportIR) -> None:
        for ws in root.iter("worksheet"):
            name = ws.get("name", "unnamed")
            mark_el = ws.find(".//mark")
            raw_mark = mark_el.get("class") if mark_el is not None else "automatic"

            cols: list[str] = []
            for col in ws.iter("column-instance"):
                c = col.get("column")
                if c:
                    cols.append(c.strip("[]"))
            if not cols:
                for col in ws.iter("column"):
                    c = col.get("caption") or col.get("name")
                    if c:
                        cols.append(c.strip("[]"))

            ir.visuals.append(
                VizIR(
                    name=name,
                    mark_type=_normalize_mark(raw_mark),
                    columns=sorted(set(cols)),
                    raw_mark=raw_mark or "",
                )
            )

    @staticmethod
    def _extract_advanced_features(root: ET.Element, ir: ReportIR) -> None:
        calc = sum(1 for _ in root.iter("calculation"))
        if calc:
            ir.unknown_features.append(f"calculated_fields:{calc}")
        if any((ds.get("name") or "").lower() == "parameters" for ds in root.iter("datasource")):
            ir.unknown_features.append("parameters:present")
        actions = sum(1 for _ in root.iter("action"))
        if actions:
            ir.unknown_features.append(f"actions:{actions}")
