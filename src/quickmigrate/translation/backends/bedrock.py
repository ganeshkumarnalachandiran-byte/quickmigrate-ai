"""Amazon Bedrock backend. boto3 is imported lazily so mock mode needs no AWS."""

from __future__ import annotations

import json
import logging

from .base import LLMBackend
from ..prompts import SYSTEM_PROMPT
from ...config import Settings
from ...errors import BackendError
from ...models import ReportIR

log = logging.getLogger(__name__)


class BedrockBackend(LLMBackend):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None  # created lazily

    def _get_client(self):
        if self._client is None:
            try:
                import boto3  # noqa: WPS433 (intentional lazy import)
            except ImportError as exc:
                raise BackendError(
                    "boto3 is required for bedrock mode. Install it: pip install boto3"
                ) from exc
            kwargs = {}
            if self._settings.aws_region:
                kwargs["region_name"] = self._settings.aws_region
            self._client = boto3.client("bedrock-runtime", **kwargs)
        return self._client

    def complete(self, messages: list[dict[str, str]], ir: ReportIR) -> str:
        client = self._get_client()
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self._settings.bedrock_max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": messages,
        }
        try:
            resp = client.invoke_model(
                modelId=self._settings.bedrock_model_id,
                body=json.dumps(body),
            )
            data = json.loads(resp["body"].read())
        except Exception as exc:  # noqa: BLE001 — normalize to typed error
            raise BackendError(f"Bedrock invoke_model failed: {exc}") from exc

        return "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )
