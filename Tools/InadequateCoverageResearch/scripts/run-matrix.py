#!/usr/bin/env python3
"""Run InadequateCoverage reproduction matrix for jsc and/or bun."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benches"
RESULTS = ROOT / "results"

SPEC_FAIL = re.compile(r"Speculation failure in (\S+).*?(InadequateCoverage|UnprofiledWatchpoint|\w+).*osrExitCounter = (\d+)")
SPEC_KIND = re.compile(r"Speculation failure in (\S+).*?\((?:D@\d+, )?bc#(\d+), (\w+)\)")
COMPILE = re.compile(r"compiling (\S+) with (DFG|FTL)")
VERBOSE_REOPT = re.compile(r"Entered reoptimize|Not reoptimizing|Jettison")
WATCHPOINT = re.compile(r"UnprofiledWatchpoint|Write to \w+")


def parse_log(text: str) -> dict:
    kinds: dict[str, int] = {}
    funcs: dict[str, int] = {}
    bcs: dict[str, int] = {}
    counters: list[int] = []
    compiles: list[str] = []
    for m in SPEC_KIND.finditer(text):
        func, bc, kind = m.group(1), m.group(2), m.group(3)
        kinds[kind] = kinds.get(kind, 0) + 1
        funcs[func.split("#")[0]] = funcs.get(func.split("#")[0], 0) + 1
        key = f"{func.split('#')[0]}@{bc}/{kind}"
        bcs[key] = bcs.get(key, 0) + 1
    for m in re.finditer(r"osrExitCounter = (\d+)", text):
        counters.append(int(m.group(1)))
    for m in COMPILE.finditer(text):
        compiles.append(f"{m.group(2)}:{m.group(1).split('#')[0]}")
    repro = ""
    for line in text.splitlines():
        if line.startswith("REPRO "):
            repro = line.strip()
    return {
        "repro": repro,
        "kinds": kinds,
        "funcs": funcs,
        "sites": bcs,
        "max_osr_exit_counter": max(counters) if counters else 0,
        "spec_failures": sum(kinds.values()),
        "inadequate": kinds.get("InadequateCoverage", 0),
        "compiles": compiles,
        "compile_count": len(compiles),
        "watchpoint": bool(WATCHPOINT.search(text)),
        "reopt_mentions": len(VERBOSE_REOPT.findall(text)),
    }


def run_jsc(jsc: str, script: Path, extra: list[str], module: bool) -> tuple[int, str]:
    cmd = [jsc]
    cmd += extra
    if module or script.suffix == ".mjs":
        cmd += ["-m"]
    cmd.append(str(script))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def run_bun(bun: str, script: Path, env_extra: dict[str, str]) -> tuple[int, str]:
    env = os.environ.copy()
    env.update(env_extra)
    proc = subprocess.run([bun, str(script)], capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout + proc.stderr


DIAG_JSC = [
    "--printEachOSRExit=true",
    "--verboseDFGOSRExit=true",
    "--logCompilationChanges=true",
    "--verboseOSR=true",
    "--useConcurrentJIT=false",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsc", default=os.environ.get("JSC", ""))
    ap.add_argument("--bun", default=os.environ.get("BUN", os.path.expanduser("~/.bun/bin/bun")))
    ap.add_argument("--engine", choices=("jsc", "bun", "both"), default="jsc")
    ap.add_argument("--ftl", action="store_true")
    ap.add_argument("--thresholds", default="100,1,5,1000")
    ap.add_argument("--benches", default="")
    ap.add_argument("--tag", default="run")
    args = ap.parse_args()

    benches = (
        [BENCH / name for name in args.benches.split(",") if name]
        if args.benches
        else sorted(p for p in BENCH.glob("*.js") if p.name != "_compat.js") + sorted(BENCH.glob("*.mjs"))
    )
    thresholds = [int(x) for x in args.thresholds.split(",") if x]
    RESULTS.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS / f"{args.tag}.tsv"
    rows = []

    def record(engine: str, bench: Path, threshold: int, rc: int, log: str) -> None:
        info = parse_log(log)
        log_file = RESULTS / f"{args.tag}-{engine}-{bench.stem}-t{threshold}.log"
        log_file.write_text(log)
        row = {
            "engine": engine,
            "bench": bench.name,
            "threshold": threshold,
            "rc": rc,
            "inadequate": info["inadequate"],
            "spec_failures": info["spec_failures"],
            "max_osr": info["max_osr_exit_counter"],
            "compile_count": info["compile_count"],
            "compiles": "|".join(info["compiles"][:12]),
            "sites": "|".join(f"{k}={v}" for k, v in list(info["sites"].items())[:8]),
            "watchpoint": int(info["watchpoint"]),
            "repro": info["repro"],
        }
        rows.append(row)
        print(
            f"{engine:4} {bench.name:28} t={threshold:<5} rc={rc} "
            f"IC={info['inadequate']:<5} maxOSR={info['max_osr_exit_counter']:<5} "
            f"compiles={info['compile_count']:<3} wp={int(info['watchpoint'])} {info['repro']}",
            flush=True,
        )

    if args.engine in ("jsc", "both"):
        if not args.jsc:
            print("need --jsc", file=sys.stderr)
            return 2
        for bench in benches:
            for threshold in thresholds:
                extra = DIAG_JSC + [f"--osrExitCountForReoptimization={threshold}"]
                extra.append("--useFTLJIT=true" if args.ftl or bench.stem == "case9-ftl" else "--useFTLJIT=false")
                rc, log = run_jsc(args.jsc, bench, extra, bench.suffix == ".mjs")
                record("jsc", bench, threshold, rc, log)

    if args.engine in ("bun", "both"):
        if not Path(args.bun).exists():
            print("need --bun", file=sys.stderr)
            return 2
        for bench in benches:
            if bench.suffix == ".mjs" or "global-let" in bench.name or "global-var" in bench.name or bench.name.startswith("topo-"):
                pass
            for threshold in thresholds:
                env = {
                    "BUN_JSC_printEachOSRExit": "1",
                    "BUN_JSC_verboseDFGOSRExit": "1",
                    "BUN_JSC_logCompilationChanges": "1",
                    "BUN_JSC_verboseOSR": "1",
                    "BUN_JSC_useConcurrentJIT": "0",
                    "BUN_JSC_osrExitCountForReoptimization": str(threshold),
                    "BUN_JSC_useFTLJIT": "1" if args.ftl or bench.stem == "case9-ftl" else "0",
                }
                rc, log = run_bun(args.bun, bench, env)
                record("bun", bench, threshold, rc, log)

    header = [
        "engine", "bench", "threshold", "rc", "inadequate", "spec_failures",
        "max_osr", "compile_count", "watchpoint", "compiles", "sites", "repro",
    ]
    with out_path.open("w") as fh:
        fh.write("\t".join(header) + "\n")
        for row in rows:
            fh.write("\t".join(str(row[h]) for h in header) + "\n")
    print(f"wrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
