from __future__ import annotations

from abc import ABC, abstractmethod

from sage.domain import TranslationRequest, TranslationResult


class TranslationProvider(ABC):
    @abstractmethod
    def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate one bounded unit and return code plus structured metadata."""
