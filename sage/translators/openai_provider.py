from __future__ import annotations

import json
import os
from typing import Any

from sage.domain import TranslationRequest, TranslationResult, sha256_bytes
from sage.translators.base import TranslationProvider


class OpenAITranslationProvider(TranslationProvider):
    """Explicitly selected network provider using the official Responses API."""

    def __init__(self, *, timeout_seconds: int = 60, max_retries: int = 2) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        self.model = os.environ.get("SAGE_MODEL")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required when provider=openai")
        if not self.model:
            raise RuntimeError("SAGE_MODEL is required when provider=openai")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("install SAGE with the 'openai' extra") from exc
        self.client: Any = OpenAI(
            api_key=api_key,
            timeout=float(timeout_seconds),
            max_retries=max_retries,
        )

    def translate(self, request: TranslationRequest) -> TranslationResult:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "code": {"type": "string"},
                "array_layout": {"type": "string"},
                "numerical_assumptions": {"type": "array", "items": {"type": "string"}},
                "dependencies": {"type": "array", "items": {"type": "string"}},
                "unsupported_constructs": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "object", "additionalProperties": {"type": "string"}},
                "function_map": {"type": "object", "additionalProperties": {"type": "string"}},
            },
            "required": [
                "code",
                "array_layout",
                "numerical_assumptions",
                "dependencies",
                "unsupported_constructs",
                "confidence",
                "function_map",
            ],
        }
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=request.prompt,
                input=request.source_code,
                max_output_tokens=20_000,
                store=False,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "translation_result",
                        "strict": True,
                        "schema": schema,
                    }
                },
                metadata={
                    "prompt_version": request.prompt_version,
                    "unit_id": request.unit.unit_id,
                },
            )
        except Exception as exc:
            # Deliberately omit exception text: upstream messages can echo request data.
            raise RuntimeError(f"OpenAI translation request failed ({type(exc).__name__})") from exc
        try:
            parsed = json.loads(response.output_text)
            code = str(parsed.pop("code"))
        except (AttributeError, TypeError, ValueError, KeyError) as exc:
            raise RuntimeError(
                "OpenAI response did not contain valid structured translation data"
            ) from exc
        metadata = {
            **parsed,
            "model": str(response.model),
            "response_id_hash": sha256_bytes(str(response.id).encode()),
            "prompt_version": request.prompt_version,
            "request": {"unit_id": request.unit.unit_id, "stored": False},
        }
        return TranslationResult(
            "1.0",
            "openai",
            code,
            metadata,
            sha256_bytes(response.output_text.encode()),
        )
