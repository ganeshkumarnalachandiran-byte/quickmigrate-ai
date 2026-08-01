"""
Integration test for the QuickSight executor.

Uses botocore's Stubber to fake the AWS API — verifies the real bedrock-mode code
path (idempotency check + create_dashboard) without touching AWS or needing
credentials. Skipped automatically if boto3 isn't installed.
"""

from __future__ import annotations

import pytest

boto3 = pytest.importorskip("boto3")
from botocore.stub import Stubber  # noqa: E402

from quickmigrate.config import Settings, Mode  # noqa: E402
from quickmigrate.execution.quicksight import QuickSightExecutor, _safe_id  # noqa: E402


def _bedrock_settings() -> Settings:
    return Settings(mode=Mode.BEDROCK, aws_account_id="123456789012",
                    aws_region="us-east-1")


def test_creates_dashboard_when_absent():
    ex = QuickSightExecutor(_bedrock_settings())
    client = ex._get_client()
    stub = Stubber(client)

    # A schema-valid Definition. boto3 validates this client-side BEFORE the
    # stub sees it, which is itself a useful signal: the real API requires
    # DataSetIdentifierDeclarations (exactly what our agent's retry loop learns
    # to add). A payload missing it is rejected here, no API call made.
    definition = {
        "DataSetIdentifierDeclarations": [
            {"Identifier": "ds", "DataSetArn": "arn:aws:quicksight:::dataset/0"}
        ],
        "Sheets": [{"SheetId": "s1", "Name": "Migrated", "Visuals": []}],
    }

    dash_id = _safe_id("sales_simple")
    # describe_dashboard -> NotFound (so we proceed to create)
    stub.add_client_error(
        "describe_dashboard", service_error_code="ResourceNotFoundException"
    )
    stub.add_response(
        "create_dashboard",
        {"DashboardId": dash_id, "Status": 201},
        expected_params={
            "AwsAccountId": "123456789012",
            "DashboardId": dash_id,
            "Name": "sales_simple",
            "Definition": definition,
        },
    )

    with stub:
        result = ex.create_dashboard(definition, dashboard_name="sales_simple")
    assert result.ok
    assert result.dashboard_id == dash_id
    stub.assert_no_pending_responses()


def test_skips_when_dashboard_exists():
    ex = QuickSightExecutor(_bedrock_settings())
    client = ex._get_client()
    stub = Stubber(client)

    dash_id = _safe_id("sales_simple")
    # describe_dashboard succeeds -> already exists -> skip create
    stub.add_response(
        "describe_dashboard",
        {"Dashboard": {"DashboardId": dash_id}},
        expected_params={"AwsAccountId": "123456789012", "DashboardId": dash_id},
    )

    with stub:
        result = ex.create_dashboard({"Sheets": []}, dashboard_name="sales_simple")
    assert result.ok
    assert result.dashboard_id == dash_id
    stub.assert_no_pending_responses()


def test_safe_id_sanitizes():
    assert _safe_id("Q4 Sales / Region!") == "q4-sales-region"
    assert _safe_id("") == "dashboard"
