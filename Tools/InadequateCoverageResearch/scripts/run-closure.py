#!/usr/bin/env python3
"""Final-harness A/B for InadequateCoverage closure.

Same JS is used for baseline and candidate. Thresholds 3/4/5/6 are
repeated for median/p90. Also regenerates FTL proof and 64-cold stubs.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

SPEC_KIND = re.compile(
    r"Speculation failure in (\S+).*?\((?:D@\d+, )?bc#(\d+), (\w+)\)"
)
COMPILE = re.compile(r"compiling (\S+) with (DFG|FTL)")
STUB_BYTES = re.compile(
    r"Generated JIT code for .*OSR exit.*: \[[^]]+\) ([0-9]+) bytes"
)
IC_STUB = re.compile(
    r"Generated JIT code for \S+ OSR exit #\d+.*?InadequateCoverage.*: \[[^]]+\) ([0-9]+) bytes"
)
REPRO = re.compile(r"^REPRO (.+)$", re.M)
COMPILE_TIME = re.compile(r"^\s*(.+Compile Time.*):\s+([0-9.]+) ms$", re.M)
FTLJIT = re.compile(r"FTLFunctionCall|FTLJIT")


COMMON = r"""
var out = (typeof print === "function") ? print : function (s) { console.log(s); };
var nowMs = (typeof preciseTime === "function") ? function () { return preciseTime() * 1000; } : function () { return Date.now(); };
function report(fields) {
    var parts = [];
    for (var k in fields)
        parts.push(k + "=" + fields[k]);
    out("REPRO " + parts.join(" "));
}
"""


def durable_a() -> str:
    return COMMON + r"""
(function () {
    function f(mode, object) {
        if (mode)
            return object.x;
        return 0;
    }
    noInline(f);
    if (typeof noFTL === "function")
        noFTL(f);
    var object = { x: 1 };
    var tWarm = nowMs();
    for (var i = 0; i < 8000; ++i)
        f(0, object);
    var warmupMs = nowMs() - tWarm;
    if (numberOfDFGCompiles(f) < 1)
        throw new Error("expected DFG after warmup");
    var retryBefore = reoptimizationRetryCount(f);
    var sum = 0;
    var tPhase = nowMs();
    for (var i = 0; i < 20000; ++i)
        sum += f(1, object);
    var phaseMs = nowMs() - tPhase;
    var tSteady = nowMs();
    for (var i = 0; i < 8000; ++i)
        sum += f(1, object);
    var steadyMs = nowMs() - tSteady;
    report({
        name: "A-durable", sum: sum, warmup_ms: warmupMs.toFixed(3),
        phase_ms: phaseMs.toFixed(3), steady_ms: steadyMs.toFixed(3),
        retry_before: retryBefore, retry_after: reoptimizationRetryCount(f),
        reopt: (reoptimizationRetryCount(f) > retryBefore) ? 1 : 0,
        dfg: numberOfDFGCompiles(f)
    });
})();
"""


def exact_hits(n: int) -> str:
    return COMMON + f"""
(function () {{
    function f(mode, object) {{
        if (mode)
            return object.x;
        return 0;
    }}
    noInline(f);
    if (typeof noFTL === "function")
        noFTL(f);
    var object = {{ x: 1 }};
    for (var i = 0; i < 8000; ++i)
        f(0, object);
    if (numberOfDFGCompiles(f) < 1)
        throw new Error("expected DFG after warmup");
    var retryBefore = reoptimizationRetryCount(f);
    var sum = 0;
    var tPhase = nowMs();
    for (var i = 0; i < {n}; ++i)
        sum += f(1, object);
    var phaseMs = nowMs() - tPhase;
    for (var i = 0; i < 8000; ++i)
        f(0, object);
    report({{
        name: "exact-{n}", sum: sum, phase_ms: phaseMs.toFixed(3), hits: {n},
        retry_before: retryBefore, retry_after: reoptimizationRetryCount(f),
        reopt: (reoptimizationRetryCount(f) > retryBefore) ? 1 : 0,
        dfg: numberOfDFGCompiles(f)
    }});
}})();
"""


def rare_spaced(hits: int, spacing: int) -> str:
    return COMMON + f"""
(function () {{
    function f(mode, object) {{
        if (mode)
            return object.x;
        return 0;
    }}
    noInline(f);
    if (typeof noFTL === "function")
        noFTL(f);
    var object = {{ x: 1 }};
    for (var i = 0; i < 8000; ++i)
        f(0, object);
    if (numberOfDFGCompiles(f) < 1)
        throw new Error("expected DFG after warmup");
    var retryBefore = reoptimizationRetryCount(f);
    var dfgBefore = numberOfDFGCompiles(f);
    var firstReoptHit = 0;
    var sum = 0;
    var tPhase = nowMs();
    for (var h = 0; h < {hits}; ++h) {{
        sum += f(1, object);
        if (!firstReoptHit && reoptimizationRetryCount(f) > retryBefore)
            firstReoptHit = h + 1;
        if (h + 1 < {hits}) {{
            for (var i = 0; i < {spacing}; ++i)
                f(0, object);
        }}
    }}
    var phaseMs = nowMs() - tPhase;
    report({{
        name: "rare-spaced", hits: {hits}, spacing: {spacing}, sum: sum,
        phase_ms: phaseMs.toFixed(3), first_reopt_hit: firstReoptHit,
        retry_before: retryBefore, retry_after: reoptimizationRetryCount(f),
        reopt: (reoptimizationRetryCount(f) > retryBefore) ? 1 : 0,
        dfg_before: dfgBefore, dfg_after: numberOfDFGCompiles(f)
    }});
}})();
"""


def interleaved_sites(n_sites: int, hits: int) -> str:
    arms = "\n".join(
        f"        if (mode === {i}) return objects[{i - 1}].x;"
        for i in range(1, n_sites + 1)
    )
    return COMMON + f"""
(function () {{
    function f(mode, objects) {{
{arms}
        return 0;
    }}
    noInline(f);
    if (typeof noFTL === "function")
        noFTL(f);
    var objects = [];
    for (var i = 0; i < {n_sites}; ++i)
        objects.push({{ x: i + 1 }});
    for (var i = 0; i < 8000; ++i)
        f(0, objects);
    if (numberOfDFGCompiles(f) < 1)
        throw new Error("expected DFG after warmup");
    var retryBefore = reoptimizationRetryCount(f);
    var sum = 0;
    var tPhase = nowMs();
    for (var h = 0; h < {hits}; ++h) {{
        for (var site = 1; site <= {n_sites}; ++site)
            sum += f(site, objects);
    }}
    var phaseMs = nowMs() - tPhase;
    report({{
        name: "interleaved-{n_sites}x{hits}", sum: sum, phase_ms: phaseMs.toFixed(3),
        retry_before: retryBefore, retry_after: reoptimizationRetryCount(f),
        reopt: (reoptimizationRetryCount(f) > retryBefore) ? 1 : 0,
        dfg: numberOfDFGCompiles(f), sites: {n_sites}, hits: {hits}
    }});
}})();
"""


FTL_PROOF = r"""
var out = (typeof print === "function") ? print : function (s) { console.log(s); };
var nowMs = (typeof preciseTime === "function") ? function () { return preciseTime() * 1000; } : function () { return Date.now(); };
(function () {
    var saw = { ftl: false };
    var object = { x: 1 };
    function score(mode, object) {
        saw.ftl = $vm.ftlTrue();
        if (mode)
            return object.x;
        return 0;
    }
    noInline(score);
    out("FTL_PROOF warmup_start");
    for (var i = 0; i < 8000; ++i) {
        score(0, object);
        if (i === 200 || i === 1500 || i === 3000)
            optimizeNextInvocation(score);
    }
    out("FTL_PROOF warmup_done sawFTL=" + saw.ftl + " dfg=" + numberOfDFGCompiles(score) + " retry=" + reoptimizationRetryCount(score));
    if (!saw.ftl)
        throw new Error("FTL_PROOF failed: score was not FTL before phase change");
    if (reoptimizationRetryCount(score) !== 0)
        throw new Error("FTL_PROOF failed: warmup jettisoned, retry=" + reoptimizationRetryCount(score));
    out("FTL_PROOF PHASE2_START");
    var retryBefore = reoptimizationRetryCount(score);
    var t0 = nowMs();
    var sum = 0;
    for (var i = 0; i < 40; ++i)
        sum += score(1, object);
    var elapsed = nowMs() - t0;
    out("FTL_PROOF PHASE2_DONE sum=" + sum + " phase_ms=" + elapsed.toFixed(3) + " retry_before=" + retryBefore + " retry_after=" + reoptimizationRetryCount(score) + " dfg=" + numberOfDFGCompiles(score));
})();
"""

MANY_COLD = r"""
var out = (typeof print === "function") ? print : function (s) { console.log(s); };
(function () {
    function f(mode, objects) {
""" + "\n".join(
    f"        if (mode === {i}) return objects[{i - 1}].x;" for i in range(1, 65)
) + r"""
        return 0;
    }
    noInline(f);
    if (typeof noFTL === "function")
        noFTL(f);
    var objects = [];
    for (var i = 0; i < 64; ++i)
        objects.push({ x: i + 1 });
    for (var i = 0; i < 8000; ++i)
        f(0, objects);
    var sum = 0;
    for (var mode = 1; mode <= 64; ++mode)
        sum += f(mode, objects);
    out("REPRO name=many-cold-compile dfg=" + numberOfDFGCompiles(f) + " retry=" + reoptimizationRetryCount(f) + " sum=" + sum);
})();
"""

CONCURRENT = r"""
var out = (typeof print === "function") ? print : function (s) { console.log(s); };
(function () {
    function f(mode, object) {
        if (mode)
            return object.x;
        return 0;
    }
    noInline(f);
    if (typeof noFTL === "function")
        noFTL(f);
    var object = { x: 1 };
    var i = 0;
    var maxTries = 200000;
    for (; i < maxTries && numberOfDFGCompiles(f) < 1; ++i)
        f(0, object);
    if (numberOfDFGCompiles(f) < 1)
        throw new Error("concurrent: no DFG after " + i + " calls");
    for (var j = 0; j < 2000; ++j)
        f(0, object);
    out("CONC warmup_done calls=" + i + " dfg=" + numberOfDFGCompiles(f) + " retry=" + reoptimizationRetryCount(f));
    var retryBefore = reoptimizationRetryCount(f);
    var sum = 0;
    for (var k = 0; k < 40; ++k)
        sum += f(1, object);
    out("CONC phase2_done sum=" + sum + " retry_before=" + retryBefore + " retry_after=" + reoptimizationRetryCount(f) + " dfg=" + numberOfDFGCompiles(f));
    if (sum !== 40)
        throw new Error("mode=1 never ran");
})();
"""


QUIET = [
    "--useConcurrentJIT=false",
    "--useFTLJIT=false",
    "--osrExitCountForReoptimization=1000",
    "--osrExitCountForReoptimizationFromLoop=1000",
]

FTL_FLAGS = [
    "--printEachOSRExit=true",
    "--logCompilationChanges=true",
    "--verboseOSR=true",
    "--useConcurrentJIT=false",
    "--useFTLJIT=true",
    "--useDollarVM=true",
    "--osrExitCountForReoptimization=1000",
    "--osrExitCountForReoptimizationFromLoop=1000",
    "--thresholdForFTLOptimizeAfterWarmUp=1000",
    "--thresholdForFTLOptimizeSoon=1000",
]

COST_FLAGS = [
    "--printEachOSRExit=false",
    "--logCompilationChanges=false",
    "--verboseDFGOSRExit=true",
    "--useConcurrentJIT=false",
    "--useFTLJIT=false",
    "--osrExitCountForReoptimization=1000",
    "--osrExitCountForReoptimizationFromLoop=1000",
    "--reportTotalCompileTimes=true",
]


def parse_repro(text: str) -> dict:
    out: dict[str, str] = {}
    m = REPRO.search(text)
    if not m:
        return out
    for part in m.group(1).split():
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def parse_ftl(text: str) -> dict:
    lines = text.splitlines()
    ftl_compile_idx = next((i for i, ln in enumerate(lines) if "with FTL" in ln), -1)
    phase2_idx = next((i for i, ln in enumerate(lines) if "FTL_PROOF PHASE2_START" in ln), -1)
    warmup = next((ln for ln in lines if ln.startswith("FTL_PROOF warmup_done")), "")
    done = next((ln for ln in lines if ln.startswith("FTL_PROOF PHASE2_DONE")), "")
    ic = len(SPEC_KIND.findall(text))
    ic_ftl = sum(1 for m in SPEC_KIND.finditer(text) if "InadequateCoverage" in m.group(0) and "FTL" in m.group(0))
    return {
        "ftl_before_phase2": int(ftl_compile_idx >= 0 and phase2_idx >= 0 and ftl_compile_idx < phase2_idx),
        "ftl_compile_line": ftl_compile_idx + 1 if ftl_compile_idx >= 0 else -1,
        "phase2_line": phase2_idx + 1 if phase2_idx >= 0 else -1,
        "warmup": warmup,
        "done": done,
        "ic": ic,
        "retry_after": parse_repro("REPRO " + done.replace("FTL_PROOF PHASE2_DONE ", "")).get("retry_after")
        or (re.search(r"retry_after=(\d+)", done).group(1) if re.search(r"retry_after=(\d+)", done) else ""),
    }


def run_jsc(jsc: str, source: str, extra: list[str], work: Path, tag: str) -> tuple[int, str, float]:
    script = work / f"{tag}.js"
    script.write_text(source)
    t0 = time.perf_counter()
    proc = subprocess.run([jsc, *extra, str(script)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return proc.returncode, proc.stdout or "", time.perf_counter() - t0


def percentile(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    ys = sorted(xs)
    if len(ys) == 1:
        return ys[0]
    k = (len(ys) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return ys[int(k)]
    return ys[f] * (c - k) + ys[c] * (k - f)


def summarize(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "min": min(xs),
        "median": statistics.median(xs),
        "p90": percentile(xs, 0.90),
        "p95": percentile(xs, 0.95),
        "max": max(xs),
        "mean": statistics.fmean(xs),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsc", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--thresholds", default="3,4,5,6")
    ap.add_argument("--mode", choices=("reps", "ftl", "cost", "concurrent", "all"), default="all")
    args = ap.parse_args()

    thresholds = [int(x) for x in args.thresholds.split(",") if x]
    RESULTS.mkdir(parents=True, exist_ok=True)
    work = RESULTS / f"{args.tag}-work"
    work.mkdir(parents=True, exist_ok=True)
    out: dict = {"tag": args.tag, "baseline": args.baseline, "jsc": args.jsc}

    def extra_for(t: int, flags: list[str]) -> list[str]:
        e = list(flags)
        if not args.baseline:
            e.append(f"--osrExitCountForReoptimizationFromInadequateCoverage={t}")
        return e

    if args.mode in ("reps", "all"):
        scenarios = [
            ("A", durable_a()),
            ("E5", exact_hits(5)),
            ("F6", exact_hits(6)),
            ("I32x4", interleaved_sites(32, 4)),
            ("I32x5", interleaved_sites(32, 5)),
        ]
        for spacing in (1000, 10000, 100000):
            scenarios.append((f"rare-1e{int(math.log10(spacing))}", rare_spaced(11, spacing)))
        # 1e6 is heavier: still 20 reps but only if requested via default
        scenarios.append(("rare-1e6", rare_spaced(7, 1_000_000)))

        rows = []
        summaries = {}
        for name, src in scenarios:
            for t in ([0] if args.baseline else thresholds):
                phase = []
                reopts = []
                firsts = []
                ics = []
                for rep in range(args.reps):
                    flags = list(QUIET)
                    rc, log, wall = run_jsc(
                        args.jsc, src, extra_for(t, flags), work, f"{name}-t{t}-r{rep}"
                    )
                    fields = parse_repro(log)
                    ic = len([1 for m in SPEC_KIND.finditer(log)])
                    # quiet mode has no IC logs; use retry/reopt from REPRO
                    rec = {
                        "name": name,
                        "threshold": "baseline" if args.baseline else t,
                        "rep": rep,
                        "rc": rc,
                        "wall_s": round(wall, 4),
                        "phase_ms": float(fields["phase_ms"]) if fields.get("phase_ms") else None,
                        "reopt": int(fields.get("reopt", 0) or 0),
                        "retry_after": int(fields.get("retry_after", 0) or 0),
                        "first_reopt_hit": int(fields.get("first_reopt_hit", 0) or 0),
                        "repro": fields,
                    }
                    rows.append(rec)
                    if rec["phase_ms"] is not None:
                        phase.append(rec["phase_ms"])
                    reopts.append(rec["reopt"])
                    if rec["first_reopt_hit"]:
                        firsts.append(rec["first_reopt_hit"])
                    print(
                        f"{name:14} t={rec['threshold']!s:<8} r={rep:<2} rc={rc} "
                        f"reopt={rec['reopt']} first={rec['first_reopt_hit'] or '-':<3} "
                        f"phase={rec['phase_ms'] if rec['phase_ms'] is not None else '-'} "
                        f"wall={wall:.3f}s",
                        flush=True,
                    )
                    if rc != 0:
                        (RESULTS / f"{args.tag}-{name}-t{t}-r{rep}.fail.log").write_text(log)
                key = f"{name}/t={rec['threshold']}"
                summaries[key] = {
                    "reopt_rate": sum(reopts) / len(reopts) if reopts else 0,
                    "phase_ms": summarize(phase),
                    "first_reopt_hit": summarize([float(x) for x in firsts]) if firsts else {"n": 0},
                }
        out["rep_rows"] = rows
        out["rep_summaries"] = summaries
        (RESULTS / f"{args.tag}-reps.json").write_text(json.dumps({"summaries": summaries, "rows": rows}, indent=2) + "\n")

    if args.mode in ("ftl", "all"):
        t = 5 if not args.baseline else 0
        rc, log, wall = run_jsc(args.jsc, FTL_PROOF, extra_for(5, FTL_FLAGS) if not args.baseline else [x for x in FTL_FLAGS], work, "ftl-proof")
        log_path = RESULTS / f"{args.tag}-ftl-proof.log"
        log_path.write_text(log)
        info = parse_ftl(log)
        info.update({"rc": rc, "wall_s": wall, "log": str(log_path)})
        out["ftl"] = info
        print(f"FTL rc={rc} ftl_before_phase2={info['ftl_before_phase2']} warmup={info['warmup'][:80]} done={info['done'][:100]}", flush=True)

    if args.mode in ("cost", "all"):
        t = 5 if not args.baseline else 0
        rc, log, wall = run_jsc(args.jsc, MANY_COLD, extra_for(5, COST_FLAGS) if not args.baseline else list(COST_FLAGS), work, "many-cold")
        log_path = RESULTS / f"{args.tag}-many-cold.log"
        log_path.write_text(log)
        stubs = [int(x) for x in IC_STUB.findall(log)]
        if not stubs:
            stubs = [int(x) for x in STUB_BYTES.findall(log)]
        times = {m.group(1).strip(): float(m.group(2)) for m in COMPILE_TIME.finditer(log)}
        fields = parse_repro(log)
        out["cost"] = {
            "rc": rc,
            "wall_s": wall,
            "stub_count": len(stubs),
            "stub_bytes_sum": sum(stubs),
            "stub_bytes_min": min(stubs) if stubs else 0,
            "stub_bytes_max": max(stubs) if stubs else 0,
            "stub_bytes_median": statistics.median(stubs) if stubs else 0,
            "compile_times": times,
            "repro": fields,
            "log": str(log_path),
        }
        print(f"COST rc={rc} stubs={len(stubs)} sum={sum(stubs)} med={out['cost']['stub_bytes_median']} times={times}", flush=True)

    if args.mode in ("concurrent", "all") and not args.baseline:
        flags = [
            "--useConcurrentJIT=true",
            "--useFTLJIT=false",
            "--osrExitCountForReoptimization=1000",
            "--osrExitCountForReoptimizationFromLoop=1000",
            "--osrExitCountForReoptimizationFromInadequateCoverage=5",
        ]
        rc, log, wall = run_jsc(args.jsc, CONCURRENT, flags, work, "concurrent")
        (RESULTS / f"{args.tag}-concurrent.log").write_text(log)
        out["concurrent"] = {"rc": rc, "wall_s": wall, "log": log[-2000:]}
        print(f"CONC rc={rc} wall={wall:.3f}\n{log}", flush=True)

    (RESULTS / f"{args.tag}.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {RESULTS / (args.tag + '.json')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
