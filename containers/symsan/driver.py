#!/usr/bin/env python3
"""Bounded JSONL SymSan binding driver used only inside the pinned image."""

from __future__ import annotations

import argparse
import ctypes
import json
from pathlib import Path

import symsan


class PipeMessage(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("msg_type", ctypes.c_uint16),
        ("flags", ctypes.c_uint16),
        ("instance_id", ctypes.c_uint32),
        ("addr", ctypes.c_uint64),
        ("context", ctypes.c_uint32),
        ("id", ctypes.c_uint32),
        ("label", ctypes.c_uint32),
        ("result", ctypes.c_uint64),
    ]


class GepMessage(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("ptr_label", ctypes.c_uint32),
        ("index_label", ctypes.c_uint32),
        ("ptr", ctypes.c_uint64),
        ("index", ctypes.c_int64),
        ("num_elems", ctypes.c_uint64),
        ("elem_size", ctypes.c_uint64),
        ("current_offset", ctypes.c_int64),
    ]


class MemcmpMessage(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("label", ctypes.c_uint32)]


class TableMessage(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("ptr", ctypes.c_uint64),
        ("num_elems", ctypes.c_uint64),
        ("elem_size", ctypes.c_uint64),
    ]


COND, GEP, MEMCMP, ADD_CONSTRAINT, MINIMIZE, TABLE = 0, 1, 2, 3, 10, 11
STATUS = {
    1: "invalid_task",
    2: "opt_sat",
    3: "opt_unsat",
    4: "opt_timeout",
    5: "nested_sat",
    6: "opt_sat_nested_unsat",
    7: "opt_sat_nested_timeout",
}


def emit(event: str, **fields: object) -> None:
    print(json.dumps({"event": event, **fields}, sort_keys=True), flush=True)


def parse_tasks(function, *args):
    try:
        return function(*args)
    except RuntimeError:
        emit("unsupported_expression", parser=function.__name__)
        return []


def apply(seed: bytes, solutions: list[dict[str, object]]) -> bytes:
    value = bytearray(seed)
    for solution in sorted(solutions, key=lambda item: int(item["offset"]), reverse=True):
        offset = int(solution["offset"])
        operation = int(solution["op"])
        if operation == int(symsan.OpType.SET) and offset < len(value):
            value[offset] = int(solution["val"])
        elif operation == int(symsan.OpType.INSERT) and offset <= len(value):
            value[offset:offset] = bytes(solution["data"])
        elif operation == int(symsan.OpType.DELETE) and offset < len(value):
            length = min(int(solution["len"]), len(value) - offset)
            del value[offset : offset + length]
    return bytes(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--trace-only", action="store_true")
    parser.add_argument("--no-bounds", action="store_true")
    parser.add_argument("--max-tasks", type=int, default=128)
    parser.add_argument("--max-tasks-per-seed", type=int, default=0)
    parser.add_argument("--max-corpus", type=int, default=128)
    parser.add_argument("--max-events", type=int, default=4096)
    parser.add_argument("--solver-timeout-ms", type=int, default=5000)
    parser.add_argument("seeds", nargs="+")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    generated = 0
    task_count = 0
    symsan.init(args.target, init_solver=not args.trace_only)
    try:
        for seed_index, seed_path in enumerate(args.seeds):
            if task_count >= args.max_tasks or generated >= args.max_corpus:
                break
            seed = Path(seed_path).read_bytes()
            seed_tasks = 0
            symsan.config(seed_path, args=[args.target, seed_path], bounds=int(not args.no_bounds))
            symsan.run()
            if not args.trace_only:
                symsan.reset_input([seed])
            events = 0
            while True:
                if events >= args.max_events:
                    emit("event_limit", seed=seed_index, limit=args.max_events)
                    break
                raw = symsan.read_event(ctypes.sizeof(PipeMessage), 1000)
                if len(raw) < ctypes.sizeof(PipeMessage):
                    break
                events += 1
                message = PipeMessage.from_buffer_copy(raw)
                emit(
                    "symbolic_event",
                    seed=seed_index,
                    type=int(message.msg_type),
                    label=int(message.label),
                    result=int(message.result),
                    address=int(message.addr),
                )
                tasks: list[int] = []
                if message.msg_type == GEP:
                    extra = symsan.read_event(ctypes.sizeof(GepMessage), 1000)
                    if len(extra) == ctypes.sizeof(GepMessage) and not args.trace_only:
                        gep = GepMessage.from_buffer_copy(extra)
                        tasks = parse_tasks(
                            symsan.parse_gep,
                            gep.ptr_label,
                            gep.ptr,
                            gep.index_label,
                            gep.index,
                            gep.num_elems,
                            gep.elem_size,
                            gep.current_offset,
                            False,
                        )
                elif message.msg_type == MEMCMP and message.flags:
                    size = ctypes.sizeof(MemcmpMessage) + int(message.result)
                    extra = symsan.read_event(size, 1000)
                    if len(extra) == size and not args.trace_only:
                        symsan.record_memcmp(message.label, extra[ctypes.sizeof(MemcmpMessage) :])
                elif message.msg_type == TABLE:
                    size = ctypes.sizeof(TableMessage) + int(message.result)
                    extra = symsan.read_event(size, 1000)
                    if len(extra) == size and not args.trace_only:
                        table = TableMessage.from_buffer_copy(extra)
                        symsan.record_table(table.ptr, extra[ctypes.sizeof(TableMessage) :])
                elif not args.trace_only and message.msg_type == COND:
                    tasks = parse_tasks(
                        symsan.parse_cond, message.label, message.result, message.flags
                    )
                elif not args.trace_only and message.msg_type == ADD_CONSTRAINT:
                    symsan.add_constraint(message.label, message.result)
                elif not args.trace_only and message.msg_type == MINIMIZE:
                    symsan.record_minimize(message.label)
                for task in tasks:
                    if task_count >= args.max_tasks or generated >= args.max_corpus:
                        break
                    if args.max_tasks_per_seed and seed_tasks >= args.max_tasks_per_seed:
                        break
                    task_count += 1
                    seed_tasks += 1
                    status, solutions = symsan.solve_task(task, args.solver_timeout_ms)
                    emit(
                        "solver_outcome",
                        task=int(task),
                        status=STATUS.get(status, str(status)),
                        solutions=len(solutions),
                    )
                    if solutions:
                        candidate = apply(seed, solutions)
                        path = output / f"symsan-{seed_index:04d}-{task_count:04d}.bin"
                        path.write_bytes(candidate)
                        generated += 1
            status, killed = symsan.terminate()
            emit(
                "trace_complete",
                seed=seed_index,
                events=events,
                exit_status=int(status),
                killed=bool(killed),
            )
    finally:
        symsan.destroy()
    emit("campaign_complete", tasks=task_count, generated=generated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
