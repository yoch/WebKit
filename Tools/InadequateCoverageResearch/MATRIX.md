# Reproduction matrix (independent runs)

Recorded 2026-08-25. All “hist jsc” rows use the Bun WebKit prebuilt
`jsc` from `autobuild-cb61607f1a4bae79d7701965062634dee9efb349`
(`/tmp/research/bun-webkit-hist/bun-webkit/bin/jsc`). Bun is
`1.4.1-canary.1+11fb73032`. Diagnostic flags: `useFTLJIT=0` (except
case9), `useConcurrentJIT=0`, OSR tracing on.

`IC` = count of `Speculation failure … InadequateCoverage` lines.
`maxOSR` = max printed `osrExitCounter` (often the value *before* the
triggering increment; trigger is `count > threshold`, so threshold 100
→ 101 failures on the hot function, plus 1–2 `<global>` extras).

## Why Bun ≠ naive `jsc file.js`

| Engine | Topology | t=100 IC | maxOSR | Result |
| --- | --- | ---: | ---: | --- |
| hist jsc | `var sink` top-level script | 3 | 0 | **masked**: 1 function IC then immediate recompile |
| hist jsc | `let sink` top-level script | 3 | 0 | **masked** (same) |
| hist jsc | closure `{sink}` | 103 | 100 | **reproduces** 100-exit policy |
| hist jsc | `jsc -m` module `let sink` | 103 | 100 | **reproduces** |
| hist jsc | strict + closure | 103 | 100 | reproduces |
| hist jsc | wrapper call | 103 | 100 | reproduces |
| hist jsc | inner-loop driver | 101 | 100 | reproduces |
| bun | **every** topology above, including top-level `var`/`let` | 101–103 | 100 | **always reproduces** |

Standalone `jsc` treats script-level `var`/`let sink` as a global object
binding. The first update-branch OSR exit continues in baseline, the
baseline write fires a global watchpoint, and DFG is jettisoned after
**one** InadequateCoverage. Bun (and `jsc -m`) keep `sink` off the JS
global object, so the optimized CodeBlock survives and pays the full
generic exit budget.

This is a **topology / embedding** difference, not a second JIT bug.
The policy issue itself is in JSC and is reproducible with standalone
`jsc` once state is not a global.

## Same-site phase change (case1 / case4)

| Engine | t | IC | maxOSR | phase-B ms | DFG compiles |
| --- | ---: | ---: | ---: | ---: | --- |
| hist jsc | 100 | 103 | 100 | 16.1 | 1→2 |
| hist jsc | 5 | 8 | 5 | 6.1 | 1→2 |
| hist jsc | 1 | 4 | 1 | 5.9 | 1→2 |
| hist jsc | 1000 | 1003 | 1000 | 96.8 | 1→2 |
| bun | 100 | 103 | 100 | 19.9 | n/a |
| bun | 5 | 8 | 5 | 5.6 | n/a |
| bun | 1 | 4 | 1 | 4.0 | n/a |

Original FrozenMiniSearch Bun twin: t=100 → 45 ms / IC≈106; t=1 → 8 ms /
IC≈7; t=1000 → 131 ms / IC≈1006.

## Adversarial

| Case | t=100 | t=5 | t=1 | Notes |
| --- | --- | --- | --- | --- |
| 2 distinct sites ×1 | IC=9, retry=0, dfg=1 | IC=7, **retry=1** | IC=3, **retry=1** | global-5 **aggregates** distinct sites |
| 3 rare once | IC=2, retry=0 | IC=2, retry=0 | IC=2, retry=0 | even t=1 does not jettison a single hit |
| 5 oscillate A/B | IC=102, dfg=2, retry=1 | IC=7, dfg=2 | IC=3, dfg=2 | one reopt; no compile storm |
| 6 many cold (31 arms ×3) | IC=94, retry=0 | IC=7, **retry=1** | IC=3, retry=1 | global-5 reopts after ~6 distinct cold arms |
| 7 sequential new arms | IC=705, maxOSR=400, retry=3, dfg 1→4 | IC=40, maxOSR=20 | IC=13, maxOSR=4 | **exponential backoff works** (100→200→400) |
| 8 inlined into driver | IC=101 | IC=6 | IC=2 | FromLoop is **not** selected: `DidTryToEnterInLoop` is checked on the *inlined callee*, which has no loop |
| 9 FTL allowed | IC=103 / 153 ms at t=1000 | IC=8 | IC=4 | FTL does not remove ForceOSRExit; t=100 vs t=1 time is closer because FTL compile dominates |

## Policy implications (before writing a patch)

- Immediate (t=1): rare-once is still safe (`>` needs a 2nd exit). Distinct-site and many-cold **do** jettison. Too aggressive as a *global* rule.
- Global dedicated threshold 5: helps same-site a lot; **fails case 2 and case 6** by treating distinct sites as one budget.
- Per-site 5 (reuse `osrExitCountForReoptimizationFromLoop`, no new option): same-site adapts after 6; distinct once / many-cold-×3 do not share that budget; global 100 remains the fallback; retry doubling still applies via `adjustedExitCountThreshold`.
- Delay tier-up: already exists (`desiredProfileLivenessRate` / fullness) and still left `SpecNone` on the update arm. Too global.


## Same-toolchain HEAD A/B (`5549b366` JSCOnly, clang-18 + libc++)

Unpatched binary snapshotted, then per-site patch
`f499cf9144fb` rebuilt incrementally. Global threshold forced to **1000**
so only `OSRExit::m_count` can fire early.

| Case | Unpatched IC / time | Patched IC / time |
| --- | ---: | ---: |
| 1 same-site | 1003 / 70.0 ms | **8 / 5.3 ms** |
| 2 distinct ×1 | 9, retry=0 | 9, retry=0 |
| 3 rare once | 2, retry=0 | 2, retry=0 |
| 4 phase B | 1003 / 80.3 ms | **8 / 5.5 ms** |
| 5 oscillate | 1002 / 85.7 ms | **7 / 7.8 ms** |
| 6 31 cold ×3 | 94, retry=0 | 94, retry=0 |
| 7 sequential arms | 7005, maxOSR=4000 | **40, maxOSR=20**, retry=3 |
| 8 inlined | 1001 / 89.1 ms | **6 / 5.4 ms** |
| 9 FTL | 1003 / 89.0 ms | **8 / 13.0 ms** |

Default t=100, same-site: 103 / 11.8 ms → **8 / 5.6 ms**.

Patch branch: `cursor/jsc-inadequate-coverage-persite-91da` (`f499cf9144fb`).
