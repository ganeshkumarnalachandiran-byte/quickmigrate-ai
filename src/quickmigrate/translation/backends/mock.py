"""
Deterministic offline backend.

Builds a plausible QuickSight payload directly from the IR — no network, no cost.
To PROVE the agentic retry loop works, the first attempt deliberately omits a
required field; when the loop feeds the validation error back, the second attempt
includes it. This is what makes `attempts == 2` on a clean run in mock mode.
"""

from __future__ import annotations

import json

from .base import LLMBackend
from ...models import ReportIR

_QS_TYPE = {
    "bar": "BarChartVisual",
    "line": "LineChartVisual",
    "area": "LineChartVisual",
    "text": "TableVisual",
    "square": "TableVisual",
    "circle": "ScatterPlotVisual",
}


class MockBackend(LLMBackend):
    def complete(self, messages: list[dict[str, str]], ir: ReportIR) -> str:
        # Detect a "please fix the error" follow-up turn.
        is_retry = any("ERROR from validator" in m["content"] for m in messages)

        visuals = [
            {
                "VisualId": f"viz-{idx}",
                "Type": _QS_TYPE.get(viz.mark_type, "TableVisual"),
                "Title": viz.name,
                "FieldsUsed": viz.columns,
            }
            for idx, viz in enumerate(ir.visuals)
        ]

        payload: dict = {
            "Sheets": [
                {"SheetId": "sheet-1", "Name": "Migrated", "Visuals": visuals}
            ],
        }
        # First attempt omits the required declarations to trigger self-correction.
        if is_retry:
            payload["DataSetIdentifierDeclarations"] = [
                {
                    "Identifier": ds,
                    "DataSetArn": f"arn:aws:quicksight:::dataset/{i}",
                }
                for i, ds in enumerate(ir.datasources or ["default"])
            ]

        return json.dumps(payload)
