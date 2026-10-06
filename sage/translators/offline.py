from __future__ import annotations

from pathlib import Path

from sage.domain import TranslationRequest, TranslationResult, sha256_bytes
from sage.translators.base import TranslationProvider


class OfflineFixtureProvider(TranslationProvider):
    def __init__(self, fixture: Path) -> None:
        self.fixture = fixture

    def translate(self, request: TranslationRequest) -> TranslationResult:
        code = self.fixture.read_text(encoding="utf-8")
        metadata = {
            "deterministic": True,
            "fixture": str(self.fixture),
            "prompt_version": request.prompt_version,
            "source_functions": request.unit.symbols,
            "target_functions": [],
            "function_map": {},
            "array_layout": "Defined by the selected target fixture and input decoder",
            "numerical_assumptions": ["See the selected target contract"],
            "dependencies": [],
            "unsupported_constructs": ["Inputs outside the selected target fixture domain"],
            "confidence": {"fixture": "reproducible", "equivalence": "requires validation"},
        }
        response_hash = sha256_bytes((code + "\n" + str(sorted(metadata.items()))).encode())
        return TranslationResult("1.0", "offline", code, metadata, response_hash)
