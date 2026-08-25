# Issue #4 restart: causal analysis of the resident multi-term flip

Source issue: https://github.com/yoch/frozenminisearch/issues/4

This report restarts from the original phenomenon (Node/V8 faster than
Bun/JSC only on `resident-multi`) instead of the OSR-threshold hypothesis
branch. Every experiment below uses the exact issue-4 generated bundles at
FrozenMiniSearch `e07e4d98`, fingerprint `0ebf5d2b` on every run.

Runtimes: Node v26.7.0 (issue version, official binary), Bun
`1.4.1-canary.1+11fb73032` (issue version), patched standalone JSC
`8a4c17a8…` (per-site InadequateCoverage candidate, controllable per run).
Machine: 4-core x86-64 Xeon, Ubuntu 24.04.

## 1. The flip reproduces locally, and it is context-dependent

Interleaved independent processes, shuffled order, n=15 per cell
(`scripts/run-issue4-node-vs-bun.py`, raw in
`matrices/issue4-node-vs-bun.json`):

| resident-multi median us | Node 26.7.0 | Bun canary | verdict |
| --- | ---: | ---: | --- |
| `issue4-multi-only` (multi alone) | 3808 | 2554 | Bun 1.49x faster, p=3e-6 |
| `resident-pressure` (full profile) | **1949** | 2684 | **Node 1.38x faster, p=6e-5** |

The full profile runs brand and substance searches in the same process
before multi. That context makes Node 48.8% faster on multi and makes Bun
5–21% slower. The issue's 1.44x reversal is the combination of both.

## 2. Per-search trajectories (512 first searches, n=10 per cell)

Raw: `matrices/issue4-transition-cells.json`.

| median per-search us, searches 257–512 | multi-only | full profile |
| --- | ---: | ---: |
| Node | 2653 | **1598** (−40%) |
| Bun | 2308 | **2790** (+21%) |

Key asymmetry: 512 iterations of multi itself never bring Node below
~2650, while in the full profile Node is already at ~1790 during the very
first 8 multi searches. Whatever unlocks V8 is learned from the earlier
workloads, not from multi repetitions.

## 3. What unlocks V8 (prefix decomposition, n=10 per cell)

Raw: `matrices/issue4-prefix-decomp.json`. Settled multi medians:

| prefix before multi | Node | Bun |
| --- | ---: | ---: |
| none | 3819 | 2447 |
| brand workload | 1969 | 2390 |
| substance workload | 1941 | 2432 |
| brand+substance | 1952 | 2586 |
| fuzzy workload | 2002 | 2478 |

Any complete prior workload unlocks V8 (−49%). For JSC the degradation is
cumulative: one prefix does nothing, two cost +6%, the full profile +16–21%.

Falsified explanations for the V8 unlock (all left multi at ~3600–3800):

- pure allocation churn prefix (no search code): no effect;
- `--max-semi-space-size=64`: −15% only;
- 1 / 8 / 64 / 256 / 1024 / 4096 direct `runSearch` brand calls in `main`:
  no effect;
- an inert second closure through `measureSearch` (call-site polymorphism):
  no effect;
- brand through `measureSearch` alone: no effect (3607–3675, n=6).

What does unlock it, deterministically (n=6+: 1878–2349): **one single
brand search invoked directly from `main` before the measured warmup**, in
addition to any bulk warmup. `--trace-deopt` shows no deopt loop (deopt
counts are identical in both variants and dominated by the build phase),
and `%GetOptimizationStatus` shows the same final tiers. The degraded state
is therefore permanently worse optimized code, selected by V8's early
tier-up/OSR heuristics depending on the exact first execution context —
not a deopt cycle, not GC sizing, not the harness call sites.

CPU profiles of the multi phase (windowed, per-search):

| function | cold multi (us/search) | unlocked (us/search) | ratio |
| --- | ---: | ---: | ---: |
| `combinators[AND]` | 661 | 136 | 4.9x |
| `finalizeSearchResults` | 465 | 93 | 5.0x |
| GC | 1232 | 709 | 1.7x |
| `scorePostingDoc` | 790 | 578 | 1.4x |

The permanent cold-start deficit is concentrated in the AND intersection
combiner and result finalization, plus proportionally heavier GC.

## 4. JSC side: reoptimization thresholds make the real workload worse

Patched standalone JSC, both bundles, interleaved n=12
(`matrices/jsc-resident-p5g1.json`):

| resident-multi median us | multi-only | resident-pressure |
| --- | ---: | ---: |
| P0 (per-site off, global 100) | 2211.7 | 2565.0 |
| P5 (per-site IC threshold 5) | 2264.1 (+2.4%, p=0.033) | **2923.3 (+14.0%, p=0.0002)** |
| G1 (global=1) | 2235.9 (+1.1%, p=0.36) | **2871.3 (+11.9%, p=0.0007)** |

Bun on the full profile confirms the same direction
(`matrices/bun-resident-g1.json`, n=15): `BUN_JSC_osrExitCountForReoptimization=1`
makes multi +7.3% worse (p=0.0007) and substance +11.9% worse, while making
fuzzy −39% better (p=0.015).

So on the workload that motivated the whole investigation, both the
per-site InadequateCoverage patch and the aggressive global threshold are
**harmful**: recompiling earlier from polluted feedback wastes compilation
and produces worse code. This definitively confirms parking the WebKit
candidate (fork PR #5) and closes the historical 14.5% claim.

## 5. Answers to the issue's investigation questions

1. **Where is the crossover?** It is not primarily a working-set-size
   crossover: it is a process-history effect. Multi measured alone flips to
   Bun-faster on this machine; multi measured after any other workload in
   the same process flips to Node-faster.
2. **Which phase?** On the V8 side the cold-start penalty sits in the AND
   intersection combiner (5x), result finalization (5x), scoring (1.4x)
   and GC (1.7x). Fingerprints are identical, so the work done is the
   same; only the generated code and GC behavior differ.
3. **Is GC involved?** Partially (1.7x per-search GC cost when cold), but
   inert allocation does not reproduce the effect and a large fixed
   new-space recovers only ~15%.
4. **Runtime vs engine?** Engine-level on both sides: reproduced in
   standalone JSC (pollution, threshold sensitivity) and in Node/V8
   (cold-start lock-in). Not a Bun/Node runtime-layer artifact.

## 6. Open follow-ups

- V8 mechanism: identify which early tier-up decision produces the
  permanently slower `combinators[AND]`/`finalizeSearchResults` code
  (needs feedback-vector/inlining dumps; possibly reportable upstream).
- JSC mechanism: trace which exit kinds accumulate on the shared functions
  under the full profile (BadCache/BadIdent seen previously) and why
  early recompilation makes it worse.
- Both engines leave real latency on the table on this workload: best
  observed multi is ~1600 us (unlocked V8) vs ~2200 us (JSC multi-only)
  vs ~2565–2900 us (JSC full profile).
