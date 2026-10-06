"""Instrument Einsums templates with explicit native ABI boundaries."""

import json
import os
import shlex
import subprocess
from pathlib import Path

build = Path("/work/native")
entry = json.loads((build / "compile_commands.json").read_text())[0]
args = shlex.split(entry["command"])
obj = build / args[args.index("-o") + 1]
undefined = subprocess.check_output(["nm", "-u", str(obj)], text=True)
symbols = sorted({line.split()[-1] for line in undefined.splitlines() if line.split()})
# Out-of-line C++ library functions and OpenMP calls stay native. Inline Einsums
# template bodies remain instrumented. C I/O/memory use SymSan's existing interceptors.
boundary = [s for s in symbols if s.startswith(("_Z", "__kmpc_", "omp_", "H5"))]
abi = Path("/work/native-boundaries.txt")
abi.write_text("".join(f"fun:{s}=uninstrumented\nfun:{s}=discard\n" for s in boundary))
args[0] = "/opt/symsan/bin/ko-clang++"
args[args.index("-o") + 1] = "/work/instrumented.o"
args = [a for a in args if not a.startswith("-O") and a != "-DNDEBUG"]
args += ["-O1", "-g", "-fno-vectorize", "-fno-slp-vectorize", "-mllvm", f"-taint-abilist={abi}"]
env = dict(os.environ, KO_USE_FASTGEN="1", KO_USE_NATIVE_LIBCXX="1", KO_DONT_OPTIMIZE="1")
subprocess.run(args, cwd=build, env=env, check=True)
# Ninja exposes the actual link invocation, including all upstream dependencies.
commands = subprocess.check_output(
    ["ninja", "-C", str(build), "-t", "commands", "einsums-reference"], text=True
)
link = next(line for line in reversed(commands.splitlines()) if " -o einsums-reference " in line)
link_args = shlex.split(link)
start = next(i for i, x in enumerate(link_args) if x.endswith("/clang++-18"))
link_args = link_args[start:]
if "&&" in link_args:
    link_args = link_args[: link_args.index("&&")]
link_args[0] = "/opt/symsan/bin/ko-clang++"
link_args = ["/work/instrumented.o" if x.endswith("driver.cpp.o") else x for x in link_args]
link_args[link_args.index("-o") + 1] = "/work/einsums-symsan"
subprocess.run(link_args, cwd=build, env=env, check=True)
Path("/work/instrumentation.json").write_text(
    json.dumps(
        {
            "compile_command": args,
            "link_command": link_args,
            "environment": {
                k: env[k] for k in ("KO_USE_FASTGEN", "KO_USE_NATIVE_LIBCXX", "KO_DONT_OPTIMIZE")
            },
            "native_symbols": boundary,
            "scope": "harness and instantiated Einsums templates; out-of-line "
            "dependencies are native",
        },
        indent=2,
    )
)
