#!/usr/bin/env python3
"""Normal-runtime A/B/C proof for the Bun #40477 InadequateCoverage patch.

Never mixes tracing flags into the performance tables.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPRO = ROOT / "repro" / "bun40477-repro.js"
RESULTS = ROOT / "results"

REPRO_LINE = re.compile(r"^REPRO (.+)$", re.M)
PROBE_LINE = re.compile(r"^PROBE (.+)$", re.M)
KV = re.compile(r"(\S+)=(\S+)")

UPDATES_SWEEP = (64, 128, 256, 512, 1000, 2000, 5000, 10000, 20000, 50000, 200000)


def pct(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    ys = sorted(xs)
    if len(ys) == 1:
        return ys[0]
    k = (len(ys) - 1) * p / 100.0
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return ys[lo]
    return ys[lo] * (hi - k) + ys[hi] * (k - lo)


def bootstrap_median_ci(xs: list[float], n: int = 2000, alpha: float = 0.05) -> tuple[float, float]:
    if len(xs) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(0xC0FFEE)
    meds = []
    for _ in range(n):
        sample = [xs[rng.randrange(len(xs))] for _ in range(len(xs))]
        meds.append(statistics.median(sample))
    meds.sort()
    lo = meds[int(alpha / 2 * (n - 1))]
    hi = meds[int((1 - alpha / 2) * (n - 1))]
    return (lo, hi)


def mann_whitney_u(a: list[float], b: list[float]) -> tuple[float, float]:
    """Return (U, two-sided normal-approx p). Ties get average ranks."""
    if not a or not b:
        return (float("nan"), float("nan"))
    paired = [(x, 0) for x in a] + [(y, 1) for y in b]
    paired.sort(key=lambda t: t[0])
    ranks = [0.0] * len(paired)
    i = 0
    while i < len(paired):
        j = i
        while j < len(paired) and paired[j][0] == paired[i][0]:
            j += 1
        avg = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[k] = avg
        i = j
    n1 = len(a)
    n2 = len(b)
    r1 = sum(rank for (rank, (_, grp)) in zip(ranks, paired) if grp == 0)
    u1 = r1 - n1 * (n1 + 1) / 2.0
    mu = n1 * n2 / 2.0
    # tie correction
    tie = 0.0
    i = 0
    while i < len(paired):
        j = i
        while j < len(paired) and paired[j][0] == paired[i][0]:
            j += 1
        t = j - i
        if t > 1:
            tie += t * t * t - t
        i = j
    n = n1 + n2
    sigma2 = n1 * n2 / 12.0 * ((n + 1) - tie / (n * (n - 1))) if n > 1 else 0.0
    if sigma2 <= 0:
        return (u1, 1.0)
    z = (u1 - mu) / math.sqrt(sigma2)
    # erfc-based two-sided p
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return (u1, p)


def parse_repro(text: str) -> dict:
    m = REPRO_LINE.search(text)
    if not m:
        return {}
    rec = {k: v for k, v in KV.findall(m.group(1))}
    rec["probes"] = PROBE_LINE.findall(text)
    return rec


def run_jsc(jsc: str, extra: list[str], inserts: int, updates: int, mode: str, probe: bool) -> tuple[int, str, float]:
    prelude = (
        f"var REPRO_INSERTS={inserts};"
        f"var REPRO_UPDATES={updates};"
        f'var REPRO_MODE="{mode}";'
        f"var REPRO_PROBE={str(probe).lower()};"
    )
    # useDollarVM only exposes compile counters for the insert-only settle.
    # It does not change DFG/FTL thresholds.
    cmd = [jsc, "--useDollarVM=true", *extra, "-e", prelude, str(REPRO)]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, text=True)
    wall = time.perf_counter() - t0
    return p.returncode, (p.stdout or "") + (p.stderr or ""), wall


def summarize(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    lo, hi = bootstrap_median_ci(xs)
    return {
        "n": len(xs),
        "min": min(xs),
        "p25": pct(xs, 25),
        "median": statistics.median(xs),
        "p75": pct(xs, 75),
        "p90": pct(xs, 90),
        "p95": pct(xs, 95),
        "max": max(xs),
        "mean": statistics.mean(xs),
        "median_ci95": [lo, hi],
    }


def reps_for(updates: int, default_small: int, default_large: int) -> int:
    return default_small if updates <= 2000 else default_large


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patched", required=True)
    ap.add_argument("--unpatched", default="")
    ap.add_argument("--inserts", type=int, default=20000)
    ap.add_argument("--small-reps", type=int, default=60)
    ap.add_argument("--large-reps", type=int, default=30)
    ap.add_argument("--tag", default="bun40477")
    ap.add_argument("--skip-unpatched", action="store_true")
    ap.add_argument("--include-t3-t10", action="store_true")
    args = ap.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    conditions: list[tuple[str, str, list[str]]] = []
    if args.unpatched and not args.skip_unpatched:
        conditions.append(("unpatched", args.unpatched, []))
    conditions.append(("patched-t5", args.patched, []))
    conditions.append(
        (
            "patched-disabled",
            args.patched,
            ["--osrExitCountForReoptimizationFromInadequateCoverage=1000000"],
        )
    )
    if args.include_t3_t10:
        conditions.append(
            ("patched-t3", args.patched, ["--osrExitCountForReoptimizationFromInadequateCoverage=3"])
        )
        conditions.append(
            ("patched-t10", args.patched, ["--osrExitCountForReoptimizationFromInadequateCoverage=10"])
        )

    rows: list[dict] = []
    summaries: dict[str, dict] = {}

    def measure(name: str, jsc: str, extra: list[str], mode: str, updates: int, reps: int) -> dict:
        samples: list[float] = []
        sinks: set[str] = set()
        fails = 0
        for i in range(reps):
            rc, text, _wall = run_jsc(jsc, extra, args.inserts, updates, mode, False)
            rec = parse_repro(text)
            if rc != 0 or "elapsed_ms" not in rec:
                fails += 1
                if i < 2:
                    print(f"FAIL {name} {mode} u={updates} r={i} rc={rc}\n{text[-400:]}", file=sys.stderr)
                continue
            samples.append(float(rec["elapsed_ms"]))
            sinks.add(rec.get("sink", ""))
        out = {
            "name": name,
            "mode": mode,
            "updates": updates,
            "inserts": args.inserts,
            "fails": fails,
            "sinks": sorted(sinks),
            **summarize(samples),
            "samples": samples,
        }
        rows.append(out)
        summaries[f"{name}/{mode}/{updates}"] = {k: v for k, v in out.items() if k != "samples"}
        med = out.get("median", float("nan"))
        print(
            f"{name:18} {mode:12} u={updates:<6} n={out.get('n', 0):<3} "
            f"med={med:.3f} p25={out.get('p25', float('nan')):.3f} "
            f"p75={out.get('p75', float('nan')):.3f} p90={out.get('p90', float('nan')):.3f} "
            f"fails={fails}",
            flush=True,
        )
        return out

    print("=== phase2 sweep (normal runtime: FTL+CJIT, no tracing) ===", flush=True)
    for updates in UPDATES_SWEEP:
        nrep = reps_for(updates, args.small_reps, args.large_reps)
        for name, jsc, extra in conditions:
            measure(name, jsc, extra, "phase2", updates, nrep)

    print("=== windows (same process, successive first-N updates) ===", flush=True)
    for name, jsc, extra in conditions:
        # one-shot windows still need reps; parse extra tokens from REPRO line
        samples: dict[str, list[float]] = {}
        nrep = args.small_reps
        fails = 0
        for i in range(nrep):
            rc, text, _ = run_jsc(jsc, extra, args.inserts, 0, "windows", False)
            rec = parse_repro(text)
            if rc != 0 or not rec:
                fails += 1
                continue
            for k, v in rec.items():
                if "-" in k and k[0].isdigit():
                    samples.setdefault(k, []).append(float(v))
        win_sum = {k: summarize(vs) for k, vs in samples.items()}
        summaries[f"{name}/windows"] = {"fails": fails, "windows": win_sum}
        print(f"{name:18} windows fails={fails} keys={sorted(win_sum)}", flush=True)

    print("=== steady-state controls ===", flush=True)
    for mode, updates, nrep in (
        ("insert-only", 0, args.small_reps),
        ("update-only", 20000, args.small_reps),
        ("mixed", 0, args.small_reps),
    ):
        for name, jsc, extra in conditions:
            measure(name, jsc, extra, mode, updates, nrep)

    # pairwise stats for phase2
    pairs = {}
    names = [c[0] for c in conditions]
    for updates in UPDATES_SWEEP:
        by = {}
        for name in names:
            key = f"{name}/phase2/{updates}"
            row = next((r for r in rows if r["name"] == name and r["mode"] == "phase2" and r["updates"] == updates), None)
            if row:
                by[name] = row.get("samples", [])
        if "patched-t5" in by and "patched-disabled" in by:
            u, p = mann_whitney_u(by["patched-t5"], by["patched-disabled"])
            med_p = statistics.median(by["patched-t5"]) if by["patched-t5"] else float("nan")
            med_d = statistics.median(by["patched-disabled"]) if by["patched-disabled"] else float("nan")
            pairs[f"phase2/{updates}/t5-vs-disabled"] = {
                "U": u,
                "p": p,
                "delta_ms": med_p - med_d,
                "delta_pct": (100.0 * (med_p - med_d) / med_d) if med_d else float("nan"),
            }
        if "patched-t5" in by and "unpatched" in by:
            u, p = mann_whitney_u(by["patched-t5"], by["unpatched"])
            med_p = statistics.median(by["patched-t5"]) if by["patched-t5"] else float("nan")
            med_u = statistics.median(by["unpatched"]) if by["unpatched"] else float("nan")
            pairs[f"phase2/{updates}/t5-vs-unpatched"] = {
                "U": u,
                "p": p,
                "delta_ms": med_p - med_u,
                "delta_pct": (100.0 * (med_p - med_u) / med_u) if med_u else float("nan"),
            }

    payload = {
        "tag": args.tag,
        "inserts": args.inserts,
        "repro": str(REPRO),
        "conditions": [c[0] for c in conditions],
        "summaries": summaries,
        "pairs": pairs,
    }
    outp = RESULTS / f"{args.tag}-perf.json"
    # results/ is gitignored; also write a compact committed copy later
    outp.write_text(json.dumps(payload, indent=2) + "\n")
    compact = {
        "tag": args.tag,
        "inserts": args.inserts,
        "conditions": payload["conditions"],
        "summaries": {k: v for k, v in summaries.items()},
        "pairs": pairs,
    }
    compact_path = ROOT / "matrices" / f"{args.tag}-perf-summary.json"
    compact_path.parent.mkdir(parents=True, exist_ok=True)
    compact_path.write_text(json.dumps(compact, indent=2) + "\n")
    print(f"wrote {outp} and {compact_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
