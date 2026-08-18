"""
Dataset resolver.

Before translation, discover the QuickSight datasets that ACTUALLY exist in the
account (via the caller's credentials) so the model references real dataset ARNs
instead of inventing them. This is what turns "the AI guessed an ARN" into "the
AI used a dataset that genuinely exists".

Honest boundary: this resolves the report's data needs onto datasets that are
already present in QuickSight. It does not create datasets — if none exist, the
report is flagged (the data layer is a precondition, and a natural Transform
fallback case). In mock mode it returns a deterministic fake so tests run offline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .config import Mode, Settings

log = logging.getLogger(__name__)


@dataclass
class DatasetRef:
    """A real QuickSight dataset the model can reference."""
    name: str
    arn: str


class DatasetResolver:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3  # lazy, so mock mode needs no AWS
            kwargs = {}
            if self._settings.aws_region:
                kwargs["region_name"] = self._settings.aws_region
            self._client = boto3.client("quicksight", **kwargs)
        return self._client

    def list_datasets(self) -> list[DatasetRef]:
        """Return the real datasets in the account. Empty list if none exist."""
        if self._settings.mode is not Mode.BEDROCK:
            # Mock: a deterministic fake so offline tests have something to map to.
            return [
                DatasetRef(
                    name="mock-dataset",
                    arn="arn:aws:quicksight:mock:000000000000:dataset/mock",
                )
            ]

        account = self._settings.aws_account_id
        client = self._get_client()
        refs: list[DatasetRef] = []
        try:
            # list_data_sets is paginated; one page is plenty for a POC, but
            # paginate properly so it doesn't silently truncate.
            paginator = client.get_paginator("list_data_sets")
            for page in paginator.paginate(AwsAccountId=account):
                for summary in page.get("DataSetSummaries", []):
                    refs.append(
                        DatasetRef(
                            name=summary.get("Name", ""),
                            arn=summary.get("Arn", ""),
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            log.warning("dataset resolution failed", extra={"error": str(exc)})
            # Return empty; orchestrator treats "no datasets" as a flag reason.
            return []

        log.debug("resolved datasets", extra={"count": len(refs)})
        return refs