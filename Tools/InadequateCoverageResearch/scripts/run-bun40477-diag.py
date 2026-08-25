#!/usr/bin/env python3
"""Diagnostic (tracing) pass for the Bun #40477 reproducer.

Never mix these numbers into the normal-runtime performance table.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPRO = ROOT / "repro" / "bun40477-repro.js"

SPEC = re.compile(
    r"Speculation failure in (\S+).*?\((?:D@\d+, )?bc#(\d+), (\w+)\)"
)
COMPILE = re.compile(r"compiling (\S+) with (DFG|FTL)")
INSTALL = re.compile(r"Installing (\S+)")
REPRO_LINE = re.compile(r"^REPRO (.+)$", re.M)
PROBE = re.compile(r"^PROBE (.+)$", re.M)
FTL_FN = re.compile(r"FTLFunctionCall")


def run(jsc: str, extra: list[str], inserts: int, updates: int, concurrent: bool) -> str:
    prelude = (
        f"var REPRO_INSERTS={inserts};var REPRO_UPDATES={updates};"
        'var REPRO_MODE="phase2";var REPRO_PROBE=true;'
    )
    flags = [
        "--useDollarVM=true",
        "--printEachOSRExit=true",
        "--verboseOSR=true",
        "--reportCompileTimes=true",
    ]
    if not concurrent:
        flags.append("--useConcurrentJIT=false")
    cmd = [jsc, *flags, *extra, "-e", prelude, str(REPRO)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return (p.stdout or "") + (p.stderr or "")


def analyze(text: str) -> dict:
    specs = SPEC.findall(text)
    kinds = Counter(k for _, _, k in specs)
    sites = Counter((fn.split("#")[0], bc, k) for fn, bc, k in specs)
    compiles = COMPILE.findall(text)
    installs = INSTALL.findall(text)
    ftl_before = False
    phase_mark = text.find("PROBE after_inserts")
    if phase_mark < 0:
        phase_mark = text.find("REPRO ")
    ftl_install_before = any(
        "FTLFunctionCall" in line and i < phase_mark
        for i, line in enumerate(text.splitlines())
        if "Installing" in line or "with FTL" in line
    )
    # simpler: FTL compile line number vs PROBE after_inserts line number
    lines = text.splitlines()
    ftl_line = next((i + 1 for i, l in enumerate(lines) if "with FTL" in l), 0)
    probe_line = next((i + 1 for i, l in enumerate(lines) if "PROBE after_inserts" in l), 0)
    ftl_before = bool(ftl_line and probe_line and ftl_line < probe_line)
    repro = REPRO_LINE.search(text)
    return {
        "repro": repro.group(1) if repro else "",
        "probes": PROBE.findall(text),
        "ic": kinds.get("InadequateCoverage", 0),
        "kinds": dict(kinds),
        "top_sites": [
            {"fn": fn, "bc": bc, "kind": k, "n": n}
            for (fn, bc, k), n in sites.most_common(8)
        ],
        "compiles": [{"fn": fn, "tier": tier} for fn, tier in compiles],
        "ftl_compile_line": ftl_line,
        "probe_after_inserts_line": probe_line,
        "ftl_before_phase2": ftl_before,
        "installs_ftl": sum(1 for x in installs if "FTLFunctionCall" in x),
        "log_chars": len(text),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patched", required=True)
    ap.add_argument("--unpatched", default="")
    ap.add_argument("--inserts", type=int, default=20000)
    ap.add_argument("--updates", type=int, default=400)
    ap.add_argument("--tag", default="bun40477")
    args = ap.parse_args()

    cases = []
    if args.unpatched:
        cases.append(("unpatched", args.unpatched, []))
    cases.append(("patched-t5", args.patched, []))
    cases.append(
        (
            "patched-disabled",
            args.patched,
            ["--osrExitCountForReoptimizationFromInadequateCoverage=1000000"],
        )
    )

    out = {"tag": args.tag, "inserts": args.inserts, "updates": args.updates, "cases": {}}
    for name, jsc, extra in cases:
        print(f"diag {name} ...", flush=True)
        text = run(jsc, extra, args.inserts, args.updates, concurrent=False)
        info = analyze(text)
        out["cases"][name] = info
        logp = ROOT / "results" / f"{args.tag}-diag-{name}.log"
        logp.parent.mkdir(parents=True, exist_ok=True)
        logp.write_text(text)
        print(
            f"  ic={info['ic']} ftl_before={info['ftl_before_phase2']} "
            f"ftl_line={info['ftl_compile_line']} probe={info['probe_after_inserts_line']} "
            f"sites={info['top_sites'][:2]} probes={info['probes']}",
            flush=True,
        )

    dest = ROOT / "matrices" / f"{args.tag}-diag.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
