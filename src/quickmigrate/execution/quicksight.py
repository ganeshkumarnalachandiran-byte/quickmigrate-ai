"""
QuickSight executor.

Takes a validated payload and creates the dashboard via boto3. This is the REAL
validator in bedrock mode — a malformed payload is rejected here, and that
rejection is what a future version could feed back into the agent for another
self-correction round.

Idempotency: before creating, we check whether a dashboard with the derived id
already exists. This makes re-running a batch safe — a half-finished run won't
collide on the second pass. (In mock mode this is a no-op.)
"""

from __future__ import annotations

import logging
import re

from ..config import Mode, Settings
from ..models import ExecutionResult

log = logging.getLogger(__name__)


def _safe_id(name: str) -> str:
    """QuickSight dashboard ids allow alnum and hyphen."""
    slug = re.sub(r"[^A-Za-z0-9-]+", "-", name.strip().lower()).strip("-")
    return slug or "dashboard"


class QuickSightExecutor:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3  # noqa: WPS433

            kwargs = {}
            if self._settings.aws_region:
                kwargs["region_name"] = self._settings.aws_region
            self._client = boto3.client("quicksight", **kwargs)
        return self._client

    def _exists(self, account: str, dash_id: str) -> bool:
        client = self._get_client()
        try:
            client.describe_dashboard(AwsAccountId=account, DashboardId=dash_id)
            return True
        except Exception:  # noqa: BLE001 — ResourceNotFound => False
            return False

    def create_dashboard(self, payload: dict, dashboard_name: str) -> ExecutionResult:
        dash_id = _safe_id(dashboard_name)

        if self._settings.mode is not Mode.BEDROCK:
            # Mock: pretend success, deterministic id, no AWS.
            return ExecutionResult(ok=True, dashboard_id=f"mock-{dash_id}")

        account = self._settings.aws_account_id
        if not account:
            return ExecutionResult(
                ok=False, dashboard_id=None,
                error="QM_AWS_ACCOUNT_ID not set",
            )

        try:
            if self._exists(account, dash_id):
                log.info("dashboard already exists; skipping", extra={"id": dash_id})
                return ExecutionResult(ok=True, dashboard_id=dash_id)

            client = self._get_client()
            client.create_dashboard(
                AwsAccountId=account,
                DashboardId=dash_id,
                Name=dashboard_name,
                Definition=payload,
            )
            return ExecutionResult(ok=True, dashboard_id=dash_id)
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(ok=False, dashboard_id=None, error=str(exc))
