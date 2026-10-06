from __future__ import annotations

import contextlib
import json
import resource
import subprocess
import time
from pathlib import Path
from typing import Any

from sage.domain import ExecutionResult


class SandboxedRunner:
    def __init__(
        self, timeout_seconds: int, max_memory_mb: int, max_output_bytes: int = 10_485_760
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.max_output_bytes = max_output_bytes

    def _limits(self) -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (self.timeout_seconds, self.timeout_seconds + 1))
        # RLIMIT_AS is not reliably enforced on macOS; it remains effective in Linux CI/containers.
        with contextlib.suppress(ValueError, OSError):
            resource.setrlimit(resource.RLIMIT_AS, (self.max_memory_bytes, self.max_memory_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (self.max_output_bytes, self.max_output_bytes))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))

    def execute(
        self, implementation: str, binary: Path, input_path: Path, case_id: str
    ) -> ExecutionResult:
        started = time.monotonic()
        timed_out = False
        exit_code: int | None = None
        stdout = ""
        stderr = ""
        outputs: dict[str, list[list[float]]] | None = None
        try:
            completed = subprocess.run(
                [str(binary), str(input_path)],
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
                preexec_fn=self._limits,
            )
            exit_code = completed.returncode
            raw_stdout = completed.stdout[: self.max_output_bytes]
            raw_stderr = completed.stderr[: self.max_output_bytes]
            stdout = raw_stdout.decode("utf-8", errors="replace")
            stderr = raw_stderr.decode("utf-8", errors="replace")
            if (
                len(completed.stdout) > self.max_output_bytes
                or len(completed.stderr) > self.max_output_bytes
            ):
                stderr += "\noutput truncated at configured bound"
                exit_code = 70
            if exit_code == 0:
                value: Any = json.loads(stdout)
                if not isinstance(value, dict):
                    raise ValueError("runner output is not an object")
                outputs = value
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = (exc.stdout or b"").decode("utf-8", errors="replace")
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            stderr += f"\nrunner protocol failure: {type(exc).__name__}: {exc}"
            exit_code = exit_code if exit_code not in (None, 0) else 70
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        return ExecutionResult(
            "1.0",
            implementation,
            case_id,
            exit_code,
            time.monotonic() - started,
            timed_out,
            stdout,
            stderr,
            outputs,
            {
                "children_max_rss_platform_units": usage.ru_maxrss,
                "user_seconds_cumulative": usage.ru_utime,
            },
        )
