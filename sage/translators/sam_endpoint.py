from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from sage.domain import TranslationRequest, TranslationResult, sha256_bytes
from sage.translators.base import TranslationProvider


class SAMEndpointProvider(TranslationProvider):
    """Adapter contract for a future SAM-compatible endpoint; no model is implied."""

    def __init__(self, endpoint: str | None = None, timeout_seconds: int = 60) -> None:
        self.endpoint = endpoint or os.environ.get("SAGE_SAM_ENDPOINT")
        self.timeout_seconds = timeout_seconds
        if not self.endpoint:
            raise RuntimeError(
                "SAM provider unsupported until SAGE_SAM_ENDPOINT points to a compatible service"
            )

    def translate(self, request: TranslationRequest) -> TranslationResult:
        assert self.endpoint is not None
        body = {
            "schema_version": "1.0",
            "prompt_version": request.prompt_version,
            "unit": {
                "id": request.unit.unit_id,
                "symbols": request.unit.symbols,
                "source_sha256": request.unit.source_sha256,
            },
            "source_language": "c",
            "target_language": "rust",
            "prompt": request.prompt,
            "source_code": request.source_code,
        }
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:  # noqa: S310
                raw = response.read(10 * 1024 * 1024 + 1)
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"SAM endpoint request failed ({type(exc).__name__})") from exc
        if len(raw) > 10 * 1024 * 1024:
            raise RuntimeError("SAM endpoint response exceeded 10 MiB")
        try:
            result = json.loads(raw)
            code = result["code"]
            metadata = result["metadata"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RuntimeError("SAM endpoint returned an incompatible response schema") from exc
        return TranslationResult("1.0", "sam", code, metadata, sha256_bytes(raw))
