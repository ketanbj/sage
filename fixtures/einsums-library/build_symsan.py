"""Instrument the C input contract; execute the pinned C++ library natively.

Mixed C++ template/native tracing produced uninitialized SymSan labels in several
upstream APIs. Keep this boundary explicit in provenance; no library branch
coverage is implied by these input-harness-generated cases.
"""

import json
import os
import shlex
import subprocess
from pathlib import Path

build = Path("/work/native")
entry = json.loads((build / "compile_commands.json").read_text())[0]
native_args = shlex.split(entry["command"])
native_args[native_args.index("-o") + 1] = "/work/kernel.o"
native_args.append("-DSAGE_KERNEL_ONLY")
subprocess.run(native_args, cwd=build, check=True)
abi = Path("/work/native-boundaries.txt")
abi.write_text("fun:einsums_kernel=uninstrumented\nfun:einsums_kernel=discard\n")
args = [
    "/opt/symsan/bin/ko-clang",
    "-c",
    "/work/input_harness.c",
    "-o",
    "/work/instrumented.o",
    "-O0",
    "-g",
    "-fno-vectorize",
    "-fno-slp-vectorize",
    "-mllvm",
    f"-taint-abilist={abi}",
]
env = dict(os.environ, KO_USE_FASTGEN="1", KO_USE_NATIVE_LIBCXX="1", KO_DONT_OPTIMIZE="1")
subprocess.run(args, cwd=build, env=env, check=True)
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
link_args = ["/work/kernel.o" if x.endswith("driver.cpp.o") else x for x in link_args]
link_args.insert(1, "/work/instrumented.o")
link_args[link_args.index("-o") + 1] = "/work/einsums-symsan"
subprocess.run(link_args, cwd=build, env=env, check=True)
Path("/work/instrumentation.json").write_text(
    json.dumps(
        {
            "compile_command": args,
            "native_compile_command": native_args,
            "link_command": link_args,
            "environment": {
                k: env[k] for k in ("KO_USE_FASTGEN", "KO_USE_NATIVE_LIBCXX", "KO_DONT_OPTIMIZE")
            },
            "native_symbols": ["einsums_kernel"],
            "scope": "input-harness-only; all Einsums implementations execute natively",
            "library_branch_exploration": False,
        },
        indent=2,
    )
)
