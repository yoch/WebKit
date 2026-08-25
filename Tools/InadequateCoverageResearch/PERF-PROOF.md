# Bun #40477 patch performance proof

> Superseded by `FMS-ADVERSARIAL-RESULTS.md`, which runs the exact real
> `issue4-multi-only` workload. The historical 14.5% global-threshold result
> did not reproduce, and P0/P5/G1/G1P5 were indistinguishable.

This is the normal-runtime proof of the **final** patch (`e01f5790`,
default t=5). Tracing numbers are in a separate section and must not
be quoted as wall-time speedup.

## Reproducer

- Downstream: https://github.com/oven-sh/bun/issues/40477
- Exact source:
  https://github.com/yoch/frozenminisearch/blob/61d4ee365fd31369bd07fa89cf9d26c596926dfb/benchmarks/jsc/inadequate-coverage-repro.js
- Standalone copy: `repro/bun40477-repro.js`

Only intentional difference: `sink` is closed over by an IIFE. A
mutable shell global is a watchpoint in standalone JSC and historically
jettisoned the CodeBlock after the first store (false negative).
`Map.get`, existing/new branch, `result.score +=`, score formula, and
insert→update phases are unchanged.

This is the Bun #40477 reproducer running in current standalone JSC.

## Build

| | SHA / binary |
| --- | --- |
| Upstream HEAD at this run | `f198e8af3b2af94d6582b4c64ff061f4c433dcb7` |
| Policy files vs `f05fd6d8` | unchanged |
| Unpatched binary | `/tmp/ic-research-v2/unpatched-f05` (JSC reopt files from `f05fd6d8`; lib sha `c54efc16…`) |
| Patched binary | `/tmp/ic-research-v2/candidate-clean` = `e01f57903d9e` (parent `f05fd6d8`) |
| Compiler | Ubuntu clang 18.1.3 + libc++, JSCOnly Release `-j4` |
| Main flags | FTL ON, concurrent JIT ON, **no** verbose OSR, **no** printEachOSRExit, global `osrExitCountForReoptimization=100` untouched |

Condition C is the same patched binary with
`--osrExitCountForReoptimizationFromInadequateCoverage=1000000`.

Unpatched and patched are not a byte-identical tree: three unrelated
JSC files differ between the v2 working tree and `f05fd6d8`. The
decisive same-codegen control is **B vs C**.

## Normal runtime performance (phase2 only, INSERTS=20000)

60 reps (30 for ≥5k). Median ms. Delta = patched-t5 − disabled (same binary).

| UPDATES | unpatched | t=5 | disabled | Δ ms | Δ % | MW p (t5 vs disabled) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 64 | 0.057 | 0.061 | 0.058 | +0.003 | +4.6 | 3e-6 |
| 128 | 0.066 | 0.069 | 0.068 | +0.001 | +1.6 | 0.028 |
| 256 | 0.080 | 0.089 | 0.078 | +0.011 | +14.1 | 5e-12 |
| 512 | 0.119 | 0.121 | 0.122 | −0.000 | −0.1 | 0.45 |
| 1000 | 0.184 | 0.185 | 0.179 | +0.006 | +3.1 | 0.41 |
| 2000 | 0.307 | 0.300 | 0.301 | −0.001 | −0.2 | 0.90 |
| 5000 | 0.481 | 0.475 | 0.485 | −0.010 | −2.0 | 0.11 |
| 10000 | 0.612 | 0.664 | 0.644 | +0.020 | +3.1 | 0.38 |
| 20000 | 0.822 | 0.798 | 0.811 | −0.014 | −1.7 | 0.79 |
| 50000 | 1.230 | 1.249 | 1.238 | +0.011 | +0.9 | 0.97 |
| 200000 | 3.304 | 3.286 | 3.308 | −0.022 | −0.7 | 0.73 |

There is **no** region where t=5 is both faster and robust. At 64–256
(the global fallback has not fired at 64, but does around the 101st exit
at 128/256) t=5 is slightly *slower* (recompile paid inside the window).
Above ~512 the delta is noise around zero. t=3 / t=10 match t=5 within
the same noise.

Do not cite older 50–90% figures: those were verbose-OSR artifacts.

## Transition windows (same process, medians, ms)

| window | unpatched | t=5 | disabled |
| --- | ---: | ---: | ---: |
| 1–8 | 0.036 | 0.040 | 0.038 |
| 9–16 | 0.003 | 0.003 | 0.003 |
| 17–32 | 0.002 | 0.002 | 0.001 |
| 33–64 | 0.003 | 0.004 | 0.003 |
| 65–128 | 0.010 | 0.007 | 0.010 |
| 129–256 | 0.012 | 0.017 | 0.012 |
| 257–512 | 0.041 | 0.029 | 0.040 |
| 513–1024 | 0.072 | 0.073 | 0.073 |
| 1025–2048 | 0.153 | 0.155 | 0.160 |
| 2049–4096 | 0.156 | 0.147 | 0.150 |

No isolated “first 100 updates” cliff. Cost of ~95 extra exits is
small versus Map/score work and versus one DFG compile.

## Diagnostic (tracing, no-CJIT — not a perf table)

Same repro, UPDATES=400, `--printEachOSRExit --verboseOSR --useConcurrentJIT=false`.

| | InadequateCoverage | site | retry after phase2 |
| --- | ---: | --- | --- |
| unpatched | **101** | `scorePostingDoc` bc#77 | 1 (global 100) |
| patched t=5 | **6** | same | 1 (per-site) |
| patched disabled | **101** | same | 1 (global 100) |

DFG installed before phase2 (`dfg=1 retry=0`). FTL was not required
for this count.

FTL-before-phase2 (separate script, 120k insert-only, `$vm.ftlTrue()`
assigned every call): `sawFTL=true retry=0` then phase2. That probe
changes bytecode, so its exit counts are **not** the authoritative
101/6. Authoritative site remains `scorePostingDoc` bc#77 in the
unmodified repro.

## Steady-state controls (median ms, 60 reps)

| mode | unpatched | t=5 | disabled |
| --- | ---: | ---: | ---: |
| insert-only (20k) | 2.745 | 2.865 | 2.796 |
| update-only after profile (20k) | 0.440 | 0.438 | 0.437 |
| mixed insert+update from the start | 2.974 | 3.102 | 2.969 |

No clear regression on the compiled update path. Insert-only / mixed
are noisy and slightly worse for t=5; not a large effect.

## FrozenMiniSearch real workload

**Not executed.** The repo’s `benchmarks/jsc/` contains only this
reproducer. The 4255→3639 µs Bun-issue numbers are a *proxy*
(`osrExitCountForReoptimization=1` on Bun), not this patch. Rebuilding
Bun against two WebKits is out of scope for this environment.

## Verdict

**HEURISTIC FIX VALID BUT PERF EVIDENCE WEAK**

The patch does what it says: 101 → 6 same-site InadequateCoverage
exits on the exact Bun #40477 function, and disabling the new option
restores 101 on the same binary. Under normal FTL+concurrent JSC that
does not produce a measurable phase2 wall-time win. Do not upstream
this as a performance patch. It can still be proposed as a small
heuristic with an honest “no standalone-JSC speedup on this repro”
note.
