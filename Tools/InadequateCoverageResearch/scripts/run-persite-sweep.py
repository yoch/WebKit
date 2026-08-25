#!/usr/bin/env python3
"""Per-site InadequateCoverage threshold sweep (cases A-O).

Varies only --osrExitCountForReoptimizationFromInadequateCoverage.
Keeps the global osrExitCountForReoptimization budget at 1000 so an
early reopt cannot be explained by the generic counter.

Compare convention remains count > threshold after the stub increments
m_count: 0 = first hit, 1 = second hit, 5 = sixth hit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

SPEC_KIND = re.compile(
    r"Speculation failure in (\S+).*?\((?:D@\d+, )?bc#(\d+), (\w+)\)"
)
COMPILE = re.compile(r"compiling (\S+) with (DFG|FTL)")
JIT_TYPE = re.compile(r", (DFGJIT|FTLJIT)")
REPRO = re.compile(r"^REPRO (.+)$", re.M)
COMPILE_TIME = re.compile(r"^\s*(.+Compile Time.*):\s+([0-9.]+) ms$", re.M)
EXIT_STUB = re.compile(
    r"Generated JIT code for DFG OSR exit #(\d+).*?(\w+) from .*?: \[.*, ([0-9]+) bytes"
)
STUB_BYTES = re.compile(
    r"Generated JIT code for .*OSR exit.*: \[[^]]+\) ([0-9]+) bytes"
)
JETTISON = re.compile(r"Jettison")


COMMON_PREFIX = r"""
var out = (typeof print === "function") ? print : function (s) { console.log(s); };
var nowMs = (typeof preciseTime === "function") ? function () { return preciseTime() * 1000; } : function () { return Date.now(); };
function report(fields) {
    var parts = [];
    for (var k in fields)
        parts.push(k + "=" + fields[k]);
    out("REPRO " + parts.join(" "));
}
"""


CASES: dict[str, str] = {
    "A": COMMON_PREFIX
    + r"""
var NAME = "A-durable-same-site";
var WARMUP = 8000;
var PHASE = 20000;
var STEADY = 8000;
(function () {
    function f(mode, object) {
        if (mode)
            return object.x;
        return 0;
    }
    noInline(f);
    if (typeof noFTL === "function")
        noFTL(f);
    var objects = { x: 1 };
    var tWarm = nowMs();
    for (var i = 0; i < WARMUP; ++i)
        f(0, objects);
    var warmupMs = nowMs() - tWarm;
    var dfgBefore = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryBefore = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    if (dfgBefore < 1)
        throw new Error("expected DFG compile after warmup");
    var sum = 0;
    var tPhase = nowMs();
    for (var i = 0; i < PHASE; ++i)
        sum += f(1, objects);
    var elapsed = nowMs() - tPhase;
    var dfgAfter = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryAfter = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    var tSteady = nowMs();
    var steadyMode = 1;
    var STEADY = 8000;
    for (var s = 0; s < STEADY; ++s)
        sum += f(steadyMode, objects);
    var steadyMs = nowMs() - tSteady;
    var dfgSteady = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retrySteady = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    report({
        name: NAME, sum: sum, warmup_ms: warmupMs.toFixed(3),
        phase_ms: elapsed.toFixed(3), steady_ms: steadyMs.toFixed(3),
        dfg_before: dfgBefore, dfg_after: dfgAfter, dfg_steady: dfgSteady,
        retry_before: retryBefore, retry_after: retryAfter, retry_steady: retrySteady,
        reopt: (retryAfter > retryBefore) ? 1 : 0
    });
})();
""",
}


def exact_hits_case(name: str, hits: int) -> str:
    return (
        COMMON_PREFIX
        + f"""
var NAME = "{name}";
var WARMUP = 8000;
var HITS = {hits};
var AFTER = 8000;
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
    var tWarm = nowMs();
    for (var i = 0; i < WARMUP; ++i)
        f(0, object);
    var warmupMs = nowMs() - tWarm;
    var dfgBefore = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryBefore = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    if (dfgBefore < 1)
        throw new Error("expected DFG compile after warmup");
    var sum = 0;
    var tPhase = nowMs();
    for (var i = 0; i < HITS; ++i)
        sum += f(1, object);
    var elapsed = nowMs() - tPhase;
    var dfgAfterHits = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryAfterHits = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    var tAfter = nowMs();
    for (var i = 0; i < AFTER; ++i)
        f(0, object);
    var afterMs = nowMs() - tAfter;
    var dfgAfter = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryAfter = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    report({{
        name: NAME, sum: sum, warmup_ms: warmupMs.toFixed(3),
        phase_ms: elapsed.toFixed(3), after_ms: afterMs.toFixed(3),
        dfg_before: dfgBefore, dfg_after_hits: dfgAfterHits, dfg_after: dfgAfter,
        retry_before: retryBefore, retry_after_hits: retryAfterHits, retry_after: retryAfter,
        reopt: (retryAfterHits > retryBefore) ? 1 : 0, hits: HITS
    }});
}})();
"""
    )


def multi_site_case(name: str, hits_per_site: int, n_sites: int = 32) -> str:
    arms = "\n".join(
        f"        if (mode === {i}) return objects[{i - 1}].x;"
        for i in range(1, n_sites + 1)
    )
    return (
        COMMON_PREFIX
        + f"""
var NAME = "{name}";
var WARMUP = 8000;
var HITS = {hits_per_site};
var N = {n_sites};
(function () {{
    function f(mode, objects) {{
{arms}
        return 0;
    }}
    noInline(f);
    if (typeof noFTL === "function")
        noFTL(f);
    var objects = [];
    for (var i = 0; i < N; ++i)
        objects.push({{ x: i + 1 }});
    var tWarm = nowMs();
    for (var i = 0; i < WARMUP; ++i)
        f(0, objects);
    var warmupMs = nowMs() - tWarm;
    var dfgBefore = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryBefore = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    if (dfgBefore < 1)
        throw new Error("expected DFG compile after warmup");
    var sum = 0;
    var tPhase = nowMs();
    for (var site = 1; site <= N; ++site) {{
        for (var h = 0; h < HITS; ++h)
            sum += f(site, objects);
    }}
    var elapsed = nowMs() - tPhase;
    var dfgAfter = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryAfter = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    report({{
        name: NAME, sum: sum, warmup_ms: warmupMs.toFixed(3),
        phase_ms: elapsed.toFixed(3),
        dfg_before: dfgBefore, dfg_after: dfgAfter,
        retry_before: retryBefore, retry_after: retryAfter,
        reopt: (retryAfter > retryBefore) ? 1 : 0, hits: HITS, sites: N
    }});
}})();
"""
    )


CASES["B"] = exact_hits_case("B-exactly-1", 1)
CASES["C"] = exact_hits_case("C-exactly-2", 2)
CASES["D"] = exact_hits_case("D-exactly-3", 3)
CASES["E"] = exact_hits_case("E-exactly-5", 5)
CASES["F"] = exact_hits_case("F-exactly-6", 6)
CASES["G"] = multi_site_case("G-32x1", 1)
CASES["H"] = multi_site_case("H-32x2", 2)
CASES["I"] = multi_site_case("I-32x3", 3)
CASES["J"] = multi_site_case("J-32x6", 6)

CASES["K"] = COMMON_PREFIX + r"""
var NAME = "K-zipf";
var WARMUP = 8000;
var PHASE = 8000;
(function () {
    function f(mode, objects) {
        if (mode === 1) return objects[0].x;
        if (mode === 2) return objects[1].x;
        if (mode === 3) return objects[2].x;
        if (mode === 4) return objects[3].x;
        if (mode === 5) return objects[4].x;
        if (mode === 6) return objects[5].x;
        if (mode === 7) return objects[6].x;
        if (mode === 8) return objects[7].x;
        if (mode === 9) return objects[8].x;
        if (mode === 10) return objects[9].x;
        if (mode === 11) return objects[10].x;
        if (mode === 12) return objects[11].x;
        if (mode === 13) return objects[12].x;
        if (mode === 14) return objects[13].x;
        if (mode === 15) return objects[14].x;
        if (mode === 16) return objects[15].x;
        return 0;
    }
    noInline(f);
    if (typeof noFTL === "function")
        noFTL(f);
    var objects = [];
    for (var i = 0; i < 16; ++i)
        objects.push({ x: i + 1 });
    var tWarm = nowMs();
    for (var i = 0; i < WARMUP; ++i)
        f(0, objects);
    var warmupMs = nowMs() - tWarm;
    var dfgBefore = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryBefore = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    if (dfgBefore < 1)
        throw new Error("expected DFG compile after warmup");
    // Zipf ranks 1..16; a few heads get many hits, tail stays cold.
    var weights = [];
    var total = 0;
    for (var r = 1; r <= 16; ++r) {
        var w = 1 / r;
        weights.push(w);
        total += w;
    }
    var sum = 0;
    var tPhase = nowMs();
    var cursor = 0;
    for (var i = 0; i < PHASE; ++i) {
        cursor = (cursor + 0.6180339887498949) % 1;
        var acc = 0;
        var mode = 16;
        for (var r = 0; r < 16; ++r) {
            acc += weights[r] / total;
            if (cursor < acc) {
                mode = r + 1;
                break;
            }
        }
        sum += f(mode, objects);
    }
    var elapsed = nowMs() - tPhase;
    var dfgAfter = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryAfter = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    report({
        name: NAME, sum: sum, warmup_ms: warmupMs.toFixed(3),
        phase_ms: elapsed.toFixed(3),
        dfg_before: dfgBefore, dfg_after: dfgAfter,
        retry_before: retryBefore, retry_after: retryAfter,
        reopt: (retryAfter > retryBefore) ? 1 : 0
    });
})();
"""

CASES["L"] = COMMON_PREFIX + r"""
var NAME = "L-briefly-hot-then-gone";
var WARMUP = 8000;
var BURST = 20;
var SITES = 8;
(function () {
    function f(mode, objects) {
        if (mode === 1) return objects[0].x;
        if (mode === 2) return objects[1].x;
        if (mode === 3) return objects[2].x;
        if (mode === 4) return objects[3].x;
        if (mode === 5) return objects[4].x;
        if (mode === 6) return objects[5].x;
        if (mode === 7) return objects[6].x;
        if (mode === 8) return objects[7].x;
        return 0;
    }
    noInline(f);
    if (typeof noFTL === "function")
        noFTL(f);
    var objects = [];
    for (var i = 0; i < SITES; ++i)
        objects.push({ x: i + 1 });
    var tWarm = nowMs();
    for (var i = 0; i < WARMUP; ++i)
        f(0, objects);
    var warmupMs = nowMs() - tWarm;
    var dfgBefore = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryBefore = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    if (dfgBefore < 1)
        throw new Error("expected DFG compile after warmup");
    var sum = 0;
    var tPhase = nowMs();
    for (var site = 1; site <= SITES; ++site) {
        for (var h = 0; h < BURST; ++h)
            sum += f(site, objects);
    }
    var elapsed = nowMs() - tPhase;
    var dfgAfter = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryAfter = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    report({
        name: NAME, sum: sum, warmup_ms: warmupMs.toFixed(3),
        phase_ms: elapsed.toFixed(3),
        dfg_before: dfgBefore, dfg_after: dfgAfter,
        retry_before: retryBefore, retry_after: retryAfter,
        reopt: (retryAfter > retryBefore) ? 1 : 0, burst: BURST, sites: SITES
    });
})();
"""

CASES["M"] = COMMON_PREFIX + r"""
var NAME = "M-successive-durable-phases";
var WARMUP = 8000;
var PHASE = 8000;
var SITES = 4;
(function () {
    function f(mode, objects) {
        if (mode === 1) return objects[0].x;
        if (mode === 2) return objects[1].x;
        if (mode === 3) return objects[2].x;
        if (mode === 4) return objects[3].x;
        return 0;
    }
    noInline(f);
    if (typeof noFTL === "function")
        noFTL(f);
    var objects = [];
    for (var i = 0; i < SITES; ++i)
        objects.push({ x: i + 1 });
    var tWarm = nowMs();
    for (var i = 0; i < WARMUP; ++i)
        f(0, objects);
    var warmupMs = nowMs() - tWarm;
    var dfgBefore = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryBefore = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    if (dfgBefore < 1)
        throw new Error("expected DFG compile after warmup");
    var sum = 0;
    var tPhase = nowMs();
    for (var site = 1; site <= SITES; ++site) {
        for (var h = 0; h < PHASE; ++h)
            sum += f(site, objects);
    }
    var elapsed = nowMs() - tPhase;
    var dfgAfter = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryAfter = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    report({
        name: NAME, sum: sum, warmup_ms: warmupMs.toFixed(3),
        phase_ms: elapsed.toFixed(3),
        dfg_before: dfgBefore, dfg_after: dfgAfter,
        retry_before: retryBefore, retry_after: retryAfter,
        reopt: (retryAfter > retryBefore) ? 1 : 0, phases: SITES
    });
})();
"""

CASES["N"] = COMMON_PREFIX + r"""
var NAME = "N-short-AB-oscillation";
var WARMUP = 8000;
var PHASE = 8000;
(function () {
    function f(mode, objects) {
        if (mode === 1) return objects[0].x;
        if (mode === 2) return objects[1].x;
        return 0;
    }
    noInline(f);
    if (typeof noFTL === "function")
        noFTL(f);
    var objects = [{ x: 1 }, { x: 2 }];
    var tWarm = nowMs();
    for (var i = 0; i < WARMUP; ++i)
        f(0, objects);
    var warmupMs = nowMs() - tWarm;
    var dfgBefore = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryBefore = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    if (dfgBefore < 1)
        throw new Error("expected DFG compile after warmup");
    var sum = 0;
    var tPhase = nowMs();
    for (var i = 0; i < PHASE; ++i)
        sum += f((i & 1) + 1, objects);
    var elapsed = nowMs() - tPhase;
    var dfgAfter = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryAfter = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    report({
        name: NAME, sum: sum, warmup_ms: warmupMs.toFixed(3),
        phase_ms: elapsed.toFixed(3),
        dfg_before: dfgBefore, dfg_after: dfgAfter,
        retry_before: retryBefore, retry_after: retryAfter,
        reopt: (retryAfter > retryBefore) ? 1 : 0
    });
})();
"""

CASES["O"] = COMMON_PREFIX + r"""
var NAME = "O-long-AB-oscillation";
var WARMUP = 8000;
var BLOCK = 2000;
var ROUNDS = 4;
(function () {
    function f(mode, objects) {
        if (mode === 1) return objects[0].x;
        if (mode === 2) return objects[1].x;
        return 0;
    }
    noInline(f);
    if (typeof noFTL === "function")
        noFTL(f);
    var objects = [{ x: 1 }, { x: 2 }];
    var tWarm = nowMs();
    for (var i = 0; i < WARMUP; ++i)
        f(0, objects);
    var warmupMs = nowMs() - tWarm;
    var dfgBefore = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryBefore = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    if (dfgBefore < 1)
        throw new Error("expected DFG compile after warmup");
    var sum = 0;
    var tPhase = nowMs();
    for (var r = 0; r < ROUNDS; ++r) {
        for (var i = 0; i < BLOCK; ++i)
            sum += f(1, objects);
        for (var i = 0; i < BLOCK; ++i)
            sum += f(2, objects);
    }
    var elapsed = nowMs() - tPhase;
    var dfgAfter = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(f) : -1;
    var retryAfter = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(f) : -1;
    report({
        name: NAME, sum: sum, warmup_ms: warmupMs.toFixed(3),
        phase_ms: elapsed.toFixed(3),
        dfg_before: dfgBefore, dfg_after: dfgAfter,
        retry_before: retryBefore, retry_after: retryAfter,
        reopt: (retryAfter > retryBefore) ? 1 : 0, block: BLOCK, rounds: ROUNDS
    });
})();
"""

FTL_PROOF = r"""
var out = (typeof print === "function") ? print : function (s) { console.log(s); };
var nowMs = (typeof preciseTime === "function") ? function () { return preciseTime() * 1000; } : function () { return Date.now(); };
(function () {
    var saw = { ftl: 0 };
    var object = { x: 1 };
    function score(mode, object) {
        if ($vm.ftlTrue())
            saw.ftl = 1;
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
    out("REPRO name=many-cold-compile dfg=" + numberOfDFGCompiles(f) + " retry=" + reoptimizationRetryCount(f));
})();
"""

COUPLING = COMMON_PREFIX + r"""
var NAME = "coupling-fromloop-vs-dedicated";
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
    for (var i = 0; i < 8000; ++i)
        f(0, object);
    var retryBefore = reoptimizationRetryCount(f);
    var sum = 0;
    for (var i = 0; i < 40; ++i)
        sum += f(1, object);
    report({
        name: NAME, sum: sum,
        retry_before: retryBefore, retry_after: reoptimizationRetryCount(f),
        reopt: (reoptimizationRetryCount(f) > retryBefore) ? 1 : 0,
        dfg: numberOfDFGCompiles(f)
    });
})();
"""


DIAG = [
    "--printEachOSRExit=true",
    "--logCompilationChanges=true",
    "--verboseOSR=true",
    "--useConcurrentJIT=false",
    "--useFTLJIT=false",
    "--osrExitCountForReoptimization=1000",
    "--reportTotalCompileTimes=true",
]


def parse_log(text: str) -> dict:
    kinds: dict[str, int] = {}
    jits: dict[str, int] = {}
    sites: dict[str, int] = {}
    compiles: list[str] = []
    stub_bytes: list[int] = []
    for m in SPEC_KIND.finditer(text):
        func, bc, kind = m.group(1), m.group(2), m.group(3)
        kinds[kind] = kinds.get(kind, 0) + 1
        key = f"{func.split('#')[0]}@{bc}/{kind}"
        sites[key] = sites.get(key, 0) + 1
        jt = JIT_TYPE.search(m.group(0))
        if jt:
            jits[jt.group(1)] = jits.get(jt.group(1), 0) + 1
    for m in COMPILE.finditer(text):
        compiles.append(f"{m.group(2)}:{m.group(1).split('#')[0]}")
    for m in STUB_BYTES.finditer(text):
        stub_bytes.append(int(m.group(1)))
    counters = [int(x) for x in re.findall(r"osrExitCounter = (\d+)", text)]
    compile_times = {m.group(1).strip(): float(m.group(2)) for m in COMPILE_TIME.finditer(text)}
    repro = ""
    m = REPRO.search(text)
    if m:
        repro = m.group(1)
    return {
        "kinds": kinds,
        "jits": jits,
        "sites": sites,
        "compiles": compiles,
        "compile_count": len(compiles),
        "inadequate": kinds.get("InadequateCoverage", 0),
        "spec_failures": sum(kinds.values()),
        "max_osr": max(counters) if counters else 0,
        "stub_bytes": stub_bytes,
        "stub_bytes_sum": sum(stub_bytes),
        "stub_bytes_max": max(stub_bytes) if stub_bytes else 0,
        "compile_times": compile_times,
        "repro": repro,
        "jettison_mentions": len(JETTISON.findall(text)),
        "unknown_option": "did not recognize option" in text.lower()
        or "Unrecognized" in text
        or "is not a valid" in text,
    }


def run_jsc(jsc: str, source: str, extra: list[str], work: Path, tag: str) -> tuple[int, str, float]:
    script = work / f"{tag}.js"
    script.write_text(source)
    cmd = [jsc, *extra, str(script)]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.perf_counter() - t0
    log = proc.stdout + proc.stderr
    return proc.returncode, log, elapsed


def parse_repro(repro: str) -> dict:
    out: dict[str, str] = {}
    for part in repro.split():
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsc", required=True)
    ap.add_argument("--tag", default="persite-sweep")
    ap.add_argument("--thresholds", default="0,1,2,3,5,10")
    ap.add_argument("--cases", default="A,B,C,D,E,F,G,H,I,J,K,L,M,N,O")
    ap.add_argument("--baseline", action="store_true", help="Unpatched binary: omit dedicated option")
    ap.add_argument("--include-ftl", action="store_true")
    ap.add_argument("--include-cost", action="store_true")
    ap.add_argument("--include-coupling", action="store_true")
    args = ap.parse_args()

    thresholds = [int(x) for x in args.thresholds.split(",") if x]
    cases = [c.strip() for c in args.cases.split(",") if c.strip()]
    RESULTS.mkdir(parents=True, exist_ok=True)
    work = RESULTS / f"{args.tag}-work"
    work.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    def record(kind: str, name: str, threshold: str, rc: int, log: str, wall: float, extra: dict | None = None) -> dict:
        info = parse_log(log)
        fields = parse_repro(info["repro"])
        log_path = RESULTS / f"{args.tag}-{name}-t{threshold}.log"
        log_path.write_text(log)
        row = {
            "kind": kind,
            "name": name,
            "threshold": threshold,
            "rc": rc,
            "wall_s": round(wall, 4),
            "inadequate": info["inadequate"],
            "spec_failures": info["spec_failures"],
            "max_osr": info["max_osr"],
            "compile_count": info["compile_count"],
            "compiles": "|".join(info["compiles"][:16]),
            "jits": json.dumps(info["jits"]),
            "sites": "|".join(f"{k}={v}" for k, v in list(info["sites"].items())[:12]),
            "retry_after": fields.get("retry_after", fields.get("retry_after_hits", "")),
            "retry_before": fields.get("retry_before", ""),
            "reopt": fields.get("reopt", ""),
            "phase_ms": fields.get("phase_ms", ""),
            "dfg_compile_ms": info["compile_times"].get("DFG Compile Time", ""),
            "ftl_compile_ms": info["compile_times"].get("FTL Compile Time", ""),
            "total_compile_ms": info["compile_times"].get("Total Compile Time", ""),
            "stub_bytes_sum": info["stub_bytes_sum"],
            "unknown_option": int(info["unknown_option"]),
            "repro": info["repro"],
            "log": str(log_path),
        }
        if extra:
            row.update(extra)
        rows.append(row)
        print(
            f"{kind:10} {name:28} t={threshold:<5} rc={rc} IC={info['inadequate']:<5} "
            f"reopt={row['reopt'] or '-':<2} retry={row['retry_after'] or '-':<3} "
            f"phase_ms={row['phase_ms'] or '-':<10} wall={wall:.3f}s",
            flush=True,
        )
        return row

    for case in cases:
        if case not in CASES:
            print(f"unknown case {case}", file=sys.stderr)
            return 2
        for threshold in thresholds:
            extra = list(DIAG)
            if not args.baseline:
                extra.append(f"--osrExitCountForReoptimizationFromInadequateCoverage={threshold}")
            rc, log, wall = run_jsc(args.jsc, CASES[case], extra, work, f"{case}-t{threshold}")
            record("sweep", case, str(threshold) if not args.baseline else "baseline", rc, log, wall)

    if args.include_ftl:
        extra = [
            "--printEachOSRExit=true",
            "--logCompilationChanges=true",
            "--verboseOSR=true",
            "--useConcurrentJIT=false",
            "--useFTLJIT=true",
            "--useDollarVM=true",
            "--osrExitCountForReoptimization=1000",
            "--thresholdForFTLOptimizeAfterWarmUp=1000",
            "--thresholdForFTLOptimizeSoon=1000",
            "--osrExitCountForReoptimizationFromInadequateCoverage=5",
        ]
        if args.baseline:
            extra = [x for x in extra if "FromInadequateCoverage" not in x]
        rc, log, wall = run_jsc(args.jsc, FTL_PROOF, extra, work, "ftl-proof")
        record("ftl-proof", "ftl-proof", "5" if not args.baseline else "baseline", rc, log, wall, extra={
            "saw_compiling_ftl": int("with FTL" in log),
            "phase2_after_ftl": int(
                ("compiling" in log and "with FTL" in log and "FTL_PROOF PHASE2_START" in log)
            ),
        })

    if args.include_cost:
        extra = list(DIAG) + ["--verboseDFGOSRExit=true"]
        if not args.baseline:
            extra.append("--osrExitCountForReoptimizationFromInadequateCoverage=5")
        rc, log, wall = run_jsc(args.jsc, MANY_COLD, extra, work, "many-cold")
        record("cost", "many-cold-64", "5" if not args.baseline else "baseline", rc, log, wall)

    if args.include_coupling and not args.baseline:
        combos = [
            ("dedicated5-fromloop100", ["--osrExitCountForReoptimizationFromInadequateCoverage=5", "--osrExitCountForReoptimizationFromLoop=100"]),
            ("dedicated100-fromloop5", ["--osrExitCountForReoptimizationFromInadequateCoverage=100", "--osrExitCountForReoptimizationFromLoop=5"]),
            ("dedicated5-fromloop5", ["--osrExitCountForReoptimizationFromInadequateCoverage=5", "--osrExitCountForReoptimizationFromLoop=5"]),
        ]
        for name, opts in combos:
            extra = list(DIAG) + opts
            rc, log, wall = run_jsc(args.jsc, COUPLING, extra, work, name)
            record("coupling", name, name, rc, log, wall)

    out_json = RESULTS / f"{args.tag}.json"
    out_tsv = RESULTS / f"{args.tag}.tsv"
    out_json.write_text(json.dumps(rows, indent=2) + "\n")
    if rows:
        header = list(rows[0].keys())
        with out_tsv.open("w") as fh:
            fh.write("\t".join(header) + "\n")
            for row in rows:
                fh.write("\t".join(str(row.get(h, "")) for h in header) + "\n")
    print(f"wrote {out_json} and {out_tsv}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
