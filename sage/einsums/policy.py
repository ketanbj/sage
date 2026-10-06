from __future__ import annotations

from typing import Any

import numpy as np

from sage.domain import ComparisonResult, ExecutionResult, Outcome
from sage.einsums.domain import TensorCase


class TensorPolicy:
    def __init__(
        self,
        atol: float,
        rtol: float,
        signed_zero_equal: bool = True,
        *,
        candidate_label: str = "rust",
    ) -> None:
        self.atol, self.rtol = atol, rtol
        self.signed_zero_equal = signed_zero_equal
        self.candidate_label = candidate_label

    def compare(
        self, case: TensorCase, cpp: ExecutionResult, rust: ExecutionResult
    ) -> ComparisonResult:
        pairs: dict[str, bool] = {}
        metrics: dict[str, Any] = {}

        def result(outcome: Outcome, message: str = "") -> ComparisonResult:
            return ComparisonResult("1.0", case.case_id, outcome, pairs, metrics, {}, message)

        if cpp.timed_out or rust.timed_out:
            return result(Outcome.TIMEOUT)
        if any(x.exit_code != 0 or x.outputs is None for x in (cpp, rust)):
            return result(Outcome.CRASH)
        expected = case.reference()
        for execution in (cpp, rust):
            output = execution.outputs
            assert output is not None
            try:
                valid = (
                    set(output) == set(expected)
                    and output["shape"] == expected["shape"]
                    and output["strides"] == expected["strides"]
                    and np.asarray(output["values"], dtype=float).shape
                    == np.asarray(expected["values"]).shape
                )
            except (ValueError, TypeError, KeyError):
                valid = False
            if not valid:
                return result(Outcome.STRUCTURAL_DIFFERENCE, execution.implementation)
        assert cpp.outputs is not None and rust.outputs is not None
        for name, left, right in (
            ("cpp_vs_numpy", cpp.outputs, expected),
            (f"{self.candidate_label}_vs_numpy", rust.outputs, expected),
            (f"{self.candidate_label}_vs_cpp", rust.outputs, cpp.outputs),
        ):
            a, b = np.asarray(left["values"]), np.asarray(right["values"])
            finite = bool(np.isfinite(a).all() and np.isfinite(b).all())
            close = finite and bool(np.all(np.abs(a - b) <= self.atol + self.rtol * np.abs(b)))
            if not self.signed_zero_equal:
                zero = (a == 0) & (b == 0)
                close = close and bool(np.array_equal(np.signbit(a[zero]), np.signbit(b[zero])))
            pairs[name] = close
            metrics[name] = {"max_absolute_error": float(np.max(np.abs(a - b))) if finite else None}
        if not pairs["cpp_vs_numpy"]:
            return result(Outcome.REFERENCE_DISAGREEMENT)
        if not all(pairs.values()):
            return result(Outcome.NUMERICAL_DIFFERENCE)
        return result(Outcome.PASS)
