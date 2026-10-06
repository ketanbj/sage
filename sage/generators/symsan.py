from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sage.config import SymSanConfig
from sage.generators.base import TestGenerator


class SymSanGenerator(TestGenerator):
    """Bounded Docker interface to the pinned SymSan Python binding."""

    def __init__(
        self,
        config: SymSanConfig,
        trace_dir: Path,
        seed_files: list[Path],
        instrumented_binary: Path | None = None,
        run_dir: Path | None = None,
        *,
        decoder: Callable[[bytes, str], Any],
    ) -> None:
        self.config = config
        self.trace_dir = trace_dir
        self.seed_files = seed_files
        self.instrumented_binary = instrumented_binary
        self.run_dir = run_dir
        self.decoder = decoder
        self.outcome: dict[str, Any] = {"status": "not-run", "generated": 0}

    def generate(self) -> list[Any]:
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        if not self.config.enabled:
            return self._finish(
                [], {"status": "UNSUPPORTED", "reason": "SymSan disabled", "generated": 0}
            )
        if self.instrumented_binary is None or self.run_dir is None:
            return self._finish(
                [],
                {
                    "status": "INFRASTRUCTURE_FAILURE",
                    "reason": "SymSan instrumented binary was not built",
                    "generated": 0,
                },
            )
        try:
            check = subprocess.run(
                ["docker", "image", "inspect", self.config.image],
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return self._finish(
                [],
                {
                    "status": "INFRASTRUCTURE_FAILURE",
                    "reason": "Docker unavailable",
                    "generated": 0,
                },
            )
        if check.returncode != 0:
            return self._finish(
                [],
                {
                    "status": "INFRASTRUCTURE_FAILURE",
                    "reason": "pinned SymSan image unavailable; run make build-containers",
                    "generated": 0,
                },
            )
        relative_binary = self.instrumented_binary.resolve().relative_to(self.run_dir.resolve())
        seed_args = [
            f"/run/{path.resolve().relative_to(self.run_dir.resolve())}" for path in self.seed_files
        ]
        command = [
            "docker",
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "--network",
            "none",
            "--memory",
            f"{self.config.max_memory_mb}m",
            "--cpus",
            "1",
            "--pids-limit",
            "128",
            "--cidfile",
            str(self.trace_dir / "container.cid"),
            "-v",
            f"{self.run_dir.resolve()}:/run",
            "--entrypoint",
            "python3",
            self.config.image,
            "/run/traces/symsan-driver.py",
            "--target",
            f"/run/{relative_binary}",
            "--output",
            "/run/corpus/generated",
            "--max-tasks",
            str(self.config.max_tasks),
            "--max-tasks-per-seed",
            str(self.config.max_tasks_per_seed),
            "--max-corpus",
            str(self.config.max_corpus),
            "--max-events",
            str(max(256, self.config.max_tasks * 32)),
        ]
        if self.config.trace_only:
            command.append("--trace-only")
        if not self.config.trace_bounds:
            command.append("--no-bounds")
        command.extend(seed_args)
        shutil.copy2(
            Path(__file__).resolve().parents[2] / "containers/symsan/driver.py",
            self.trace_dir / "symsan-driver.py",
        )
        status, reason, stdout = self._invoke(command)
        valid, invalid = self._import_generated()
        solver_outcomes = []
        trace_outcomes = []
        limited_seeds = set()
        for line in stdout.decode("utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event") == "solver_outcome":
                solver_outcomes.append(event)
            elif event.get("event") == "trace_complete":
                trace_outcomes.append(event)
            elif event.get("event") == "event_limit":
                limited_seeds.add(event["seed"])
        failed_traces = [
            event
            for event in trace_outcomes
            if event["exit_status"] != 0 and event["seed"] not in limited_seeds
        ]
        if status == "COMPLETED" and failed_traces:
            status = "INFRASTRUCTURE_FAILURE"
            reason = "instrumented target failed; inspect trace_outcomes"
        outcome = {
            "status": status,
            "reason": reason,
            "trace_only": self.config.trace_only,
            "seed_count": len(self.seed_files),
            "symbolic_event_records": sum(
                1 for line in stdout.splitlines() if b'"symbolic_event"' in line
            ),
            "solver_outcomes": solver_outcomes,
            "trace_outcomes": trace_outcomes,
            "trace_bounds": self.config.trace_bounds,
            "unsupported_expressions": sum(
                1 for line in stdout.splitlines() if b'"unsupported_expression"' in line
            ),
            "invalid_generated": invalid,
            "generated": len(valid),
            "command": command,
            "bounds": {
                "timeout_seconds": self.config.timeout_seconds,
                "max_tasks": self.config.max_tasks,
                "max_tasks_per_seed": self.config.max_tasks_per_seed,
                "max_memory_mb": self.config.max_memory_mb,
                "max_output_bytes": self.config.max_output_bytes,
                "max_corpus": self.config.max_corpus,
            },
        }
        return self._finish(valid, outcome)

    def _invoke(self, command: list[str]) -> tuple[str, str, bytes]:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                timeout=self.config.timeout_seconds,
                check=False,
            )
            stdout = completed.stdout[: self.config.max_output_bytes]
            stderr = completed.stderr[: self.config.max_output_bytes]
            status = "COMPLETED" if completed.returncode == 0 else "INFRASTRUCTURE_FAILURE"
            reason = "" if completed.returncode == 0 else f"driver exit {completed.returncode}"
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or b"")[: self.config.max_output_bytes]
            stderr = (exc.stderr or b"")[: self.config.max_output_bytes]
            status = "TIMEOUT"
            reason = "bounded SymSan campaign timed out"
        except OSError as exc:
            stdout, stderr = b"", str(exc).encode()
            status, reason = "INFRASTRUCTURE_FAILURE", "SymSan process could not start"
        finally:
            cid = self.trace_dir / "container.cid"
            if cid.is_file():
                container_id = cid.read_text().strip()
                if container_id:
                    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                        subprocess.run(
                            ["docker", "rm", "-f", container_id],
                            capture_output=True,
                            timeout=15,
                            check=False,
                        )
                cid.unlink(missing_ok=True)
        (self.trace_dir / "events.jsonl").write_bytes(stdout)
        (self.trace_dir / "symsan.stderr.log").write_bytes(stderr)
        return status, reason, stdout

    def _import_generated(self) -> tuple[list[Any], int]:
        assert self.run_dir is not None
        valid: list[Any] = []
        invalid = 0
        seen = {path.read_bytes() for path in self.seed_files}
        paths = sorted((self.run_dir / "corpus" / "generated").glob("symsan-*.bin"))
        for index, path in enumerate(paths):
            try:
                payload = path.read_bytes()
                if payload in seen:
                    continue
                case_id = f"symsan-{index:04d}"
                case = self.decoder(payload, case_id)
                seen.add(payload)
                case.provenance = {
                    "origin": "symsan",
                    "generated_file": path.name,
                    "concrete_replay_required": True,
                }
                valid.append(case)
            except ValueError as exc:
                invalid += 1
                path.with_suffix(".invalid.json").write_text(
                    json.dumps({"status": "INVALID_INPUT", "reason": str(exc)}, indent=2) + "\n",
                    encoding="utf-8",
                )
        return valid, invalid

    def _finish(self, cases: list[Any], outcome: dict[str, Any]) -> list[Any]:
        self.outcome = outcome
        (self.trace_dir / "symsan-outcome.json").write_text(
            json.dumps(self.outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return cases
