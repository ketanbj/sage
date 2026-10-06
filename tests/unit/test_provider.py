from __future__ import annotations

import pytest

from sage.translators.openai_provider import OpenAITranslationProvider
from sage.translators.sam_endpoint import SAMEndpointProvider


def test_openai_is_explicit_and_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SAGE_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAITranslationProvider()


def test_sam_does_not_pretend_model_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SAGE_SAM_ENDPOINT", raising=False)
    with pytest.raises(RuntimeError, match="unsupported"):
        SAMEndpointProvider()


def test_sam_environment_variable_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAGE_SAM_ENDPOINT", "http://127.0.0.1:9999")
    provider = SAMEndpointProvider()
    assert provider.endpoint == "http://127.0.0.1:9999"


def test_explicit_sam_endpoint_overrides_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAGE_SAM_ENDPOINT", "http://127.0.0.1:9999")
    provider = SAMEndpointProvider(endpoint="http://127.0.0.1:8888")
    assert provider.endpoint == "http://127.0.0.1:8888"
