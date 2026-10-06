from __future__ import annotations

from typing import Any

from sage.summarizers.base import Summarizer


class OfflineSummarizer(Summarizer):
    def summarize(self, artifacts: dict[str, Any]) -> dict[str, Any]:
        outcomes = artifacts.get("outcomes", {})
        failures = sum(count for name, count in outcomes.items() if name != "PASS")
        return {
            "advisory": True,
            "provider": "offline-deterministic",
            "text": (
                f"Concrete validation recorded {sum(outcomes.values())} cases and "
                f"{failures} non-pass outcomes. Inspect comparisons and reproducers; "
                "this summary does not declare equivalence."
            ),
        }
