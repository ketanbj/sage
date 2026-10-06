"""Pinned, file-complete source inventory and conservative whole-library completion gate."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from sage.domain import sha256_file
from sage.targets.einsums import EINSUMS_COMMIT

# These are API probes, not assertions that their containing modules are fully ported.
PROBES = {
    "Einsums/Tensor": ["copy", "add", "multiply", "scale", "subtract", "divide", "negate", "slice"],
    "Einsums/TensorAlgebra": ["transpose", "matmul"],
    "Einsums/LinearAlgebra": [
        "dot",
        "axpy",
        "axpby",
        "gemv",
        "ger",
        "norm",
        "inverse",
        "syev_values",
        "qr_reconstruct",
    ],
    "Einsums/TensorUtilities": ["rmsd"],
    "Einsums/FFT": ["fft", "ifft", "fftfreq"],
}
GPU_MODULES = {"Einsums/GPUMemory", "Einsums/GPUStreams", "EinsumsPy/GPU"}


# Scientific functionality exists; finite probes do not establish every upstream contract.
API_IMPLEMENTATIONS = {
    "Einsums/Tensor": "api/array.rs, api/storage.rs; tensor.rs",
    "Einsums/TensorAlgebra": "api/array.rs",
    "Einsums/LinearAlgebra": "api/linalg.rs, api/mod.rs",
    "Einsums/TensorUtilities": "api/mod.rs, api/array.rs",
    "Einsums/Decomposition": "api/decomposition.rs",
    "Einsums/FFT": "api/mod.rs, fft.rs",
    "Einsums/Runtime": "api/runtime.rs",
    "Einsums/RuntimeConfiguration": "api/runtime.rs",
    "Einsums/Profile": "api/runtime.rs",
    "EinsumsPy/Core": "python/pyeinsums/core.py",
    "EinsumsPy/Tensor": "python/pyeinsums/_tensor.py",
    "EinsumsPy/LinearAlgebra": "python/pyeinsums/_linalg.py",
    "EinsumsPy/TensorAlgebra": "python/pyeinsums/core.py",
    "EinsumsPy/Errors": "python/pyeinsums/errors.py",
    "EinsumsPy/TestUtils": "python/pyeinsums/_testutils.py (safe metadata validation)",
    "Python/package": "python/einsums, python/pyeinsums; pyproject.toml",
}

CPP_API_IMPLEMENTATIONS = {
    **{
        k: v
        for k, v in API_IMPLEMENTATIONS.items()
        if k.startswith("EinsumsPy/") or k == "Python/package"
    },
    "Einsums/Tensor": "api/array.hpp, api/typed_tensor.hpp, api/storage.hpp",
    "Einsums/TensorBase": "api/array.hpp, api/typed_tensor.hpp",
    "Einsums/TensorImpl": "api/typed_tensor.hpp",
    "Einsums/TensorAlgebra": "api/array.hpp, api/execute.cpp",
    "Einsums/LinearAlgebra": "api/linalg.cpp, api/execute.cpp",
    "Einsums/TensorUtilities": "api/execute.cpp, api/array.hpp",
    "Einsums/Decomposition": "api/decomposition.hpp",
    "Einsums/FFT": "api/fft.hpp",
    "Einsums/Runtime": "api/runtime.hpp",
    "Einsums/RuntimeConfiguration": "api/runtime.hpp",
    "Einsums/Profile": "api/runtime.hpp",
    "Einsums/Errors": "api/array.hpp::Error; python/pyeinsums/errors.py",
    "Einsums/Logging": "api/runtime.hpp::log; python/pyeinsums/core.py",
}

# Internal facilities are replaced, not copied as upstream symbols/ABIs.
CPP_REPLACEMENTS = {
    "Build/install": "CMakeLists.txt, pyproject.toml, hatch_build.py",
    "Einsums/Assertion": "api/array.hpp::require and typed exceptions",
    "Einsums/BLAS": "independent array/execute operations and Eigen factorizations",
    "Einsums/BLASBase": "Eigen; upstream BLAS ABI is not exposed",
    "Einsums/BLASVendor": "Eigen; upstream vendor symbols are not exposed",
    "Einsums/BufferAllocator": "std::vector, std::shared_ptr and checked shapes",
    "Einsums/Concepts": "C++20 templates and runtime shape/dtype checks",
    "Einsums/Config": "CMake feature configuration and typed runtime configuration",
    "Einsums/Debugging": "standard exceptions and streams",
    "Einsums/HPTT": "api/array.hpp::permute and unchanged bounded scalar kernels",
    "Einsums/Iterator": "std::span range iteration and Python dtype iterators",
    "Einsums/Preprocessor": "C++20 language facilities; no upstream macro ABI",
    "Einsums/Print": "standard streams and Python tensor representation",
    "Einsums/StringUtil": "std::string and Python calling-interface utilities",
    "Einsums/TypeSupport": "api/array.hpp::DType and four typed tensor aliases",
    "Einsums/Utilities": "checked shapes/strides and standard-library utilities",
    "Einsums/Version": "pyproject.toml and Python __version__",
}


def inventory(checkout: Path) -> dict[str, Any]:
    actual = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    dirty = subprocess.check_output(
        ["git", "-C", str(checkout), "status", "--porcelain"], text=True
    ).strip()
    if actual != EINSUMS_COMMIT or dirty:
        raise ValueError("inventory requires the clean pinned Einsums checkout")
    paths = (
        subprocess.check_output(["git", "-C", str(checkout), "ls-files", "-z"]).decode().split("\0")
    )
    modules: dict[str, dict[str, Any]] = {}
    files = []
    for path in sorted(p for p in paths if p):
        p = Path(path)
        parts = p.parts
        if (
            parts[0] == "libs"
            and len(parts) > 3
            and parts[1] in ("Einsums", "EinsumsPy", "EinsumsExperimental")
        ):
            module = "/".join(parts[1:3])
        elif parts[0] == "pyeinsums":
            module = "Python/package"
        elif parts[0] in ("cmake", "CMakeLists.txt"):
            module = "Build/install"
        elif parts[0] in ("tests", "testing"):
            module = "Tests/integration"
        else:
            module = "Repository/support"
        kind = (
            "test"
            if "tests" in parts or parts[0] == "testing"
            else "runtime"
            if p.suffix in (".hpp", ".cpp", ".h", ".hip", ".py")
            else "build"
            if p.suffix == ".cmake" or p.name == "CMakeLists.txt"
            else "support"
        )
        item = {
            "path": path,
            "module": module,
            "kind": kind,
            "sha256": sha256_file(checkout / path),
            "lines": len((checkout / path).read_bytes().splitlines()),
            "accelerator": p.suffix == ".hip" or "Device" in p.name or module in GPU_MODULES,
        }
        files.append(item)
        record = modules.setdefault(
            module,
            {
                "files": [],
                "runtime_files": 0,
                "runtime_lines": 0,
                "probe_operations": PROBES.get(module, []),
            },
        )
        record["files"].append(path)
        if kind == "runtime":
            record["runtime_files"] += 1
            record["runtime_lines"] += item["lines"]
    return {
        "schema_version": "einsums-inventory-1.0",
        "commit": actual,
        "files": files,
        "modules": modules,
    }


def coverage(
    source: dict[str, Any],
    operations: dict[str, int],
    outcomes: dict[str, int],
    *,
    target_language: str = "rust",
) -> dict[str, Any]:
    if target_language not in {"rust", "cpp20"}:
        raise ValueError("unsupported coverage target language")
    implementations = CPP_API_IMPLEMENTATIONS if target_language == "cpp20" else API_IMPLEMENTATIONS
    replacements = CPP_REPLACEMENTS if target_language == "cpp20" else {}
    modules = {}
    for name, module in source["modules"].items():
        probes = module["probe_operations"]
        if name in GPU_MODULES:
            modules[name] = {
                "translation_status": "EXCLUDED_GPU",
                "runtime_files": module["runtime_files"],
                "probe_cases": {},
                "full_api_validation": False,
            }
            continue
        modules[name] = {
            "translation_status": (
                "IMPLEMENTED_WITH_CONTRACT_GAPS"
                if name in implementations
                else "REPLACED_INFRASTRUCTURE_WITH_CONTRACT_GAPS"
                if name in replacements
                else "PARTIAL"
                if probes
                else "NOT_IMPLEMENTED"
            ),
            "implementation": implementations.get(name, replacements.get(name)),
            "runtime_files": module["runtime_files"],
            "probe_cases": {op: operations.get(op, 0) for op in probes},
            "full_api_validation": False,
        }
    return {
        "schema_version": "einsums-coverage-1.0",
        "requested_scope": "cpu-python-library",
        "target_language": target_language,
        "scope_status": "INCOMPLETE_SCOPE",
        "whole_library_complete": False,
        "modules": modules,
        "outcome_counts": outcomes,
        "missing_contracts": [
            (
                "exact compatibility for every C++ public symbol/template overload "
                "and calling contract"
            ),
            "resolution of documented Python numerical/shape differences from the pinned source",
            (
                "SymSan-generated upstream validation for HDF5, decompositions, "
                "storage and runtime services"
            ),
            "complete aliasing, error, threading and large-problem behavior coverage",
            "downstream Psi4 and C++ build/install integration",
        ],
        "note": (
            "Passing bounded API probes cannot mark an upstream module or whole library complete."
        ),
    }
