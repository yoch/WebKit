# Closure pass — InadequateCoverage per-site threshold

Harness: `scripts/run-closure.py` (final). Both baseline and candidate
ran this exact script. Compare is `m_count > t` after increment
(t=5 → 6th same-site hit). 20 reps unless noted. x86_64 Linux,
clang-18.1.3 + libc++.

Binaries used for the A/B (policy files identical to current upstream
`f05fd6d8b3be`; JSC delta vs `3a999a1a` is unrelated to this option):

- baseline: `/tmp/ic-research-v2/baseline` (unpatched)
- candidate: `/tmp/ic-research-v2/candidate` (default was 3; every
  closure case passed `--osrExitCountForReoptimizationFromInadequateCoverage=N`)

## 1. Threshold 3/4/5/6 — durable phase change (case A, 20k mode=1)

| t | reopt_rate | median ms | p90 | p95 |
| --- | --- | --- | --- | --- |
| 3 | 1.00 | 0.686 | 0.749 | 0.754 |
| 4 | 1.00 | 0.685 | 0.724 | 0.732 |
| 5 | 1.00 | 0.679 | 0.714 | 0.728 |
| 6 | 1.00 | 0.693 | 0.741 | 0.760 |
| baseline (global 1000) | 1.00 | 0.699 | 0.761 | 0.769 |

t=3/4/5/6 are indistinguishable (≪ 0.1 ms). Baseline A here also
reoptimizes, via the raised global budget of 1000, after ~1001 exits.
The pass-2 84 ms figure was the same case with verbose OSR logging.

## 2. Exact-hit / interleaved spray (20/20)

| case | t=3 | t=4 | t=5 | t=6 | baseline |
| --- | --- | --- | --- | --- | --- |
| E exactly 5 then never | reopt | reopt | no | no | no |
| F exactly 6 then never | reopt | reopt | reopt | no | no |
| 32 sites ×4 interleaved | reopt | no | no | no | no |
| 32 sites ×5 interleaved | reopt | reopt | no | no | no |

## 3. Rare spaced hits (same site, m_count never decays)

Warmup mode=0, then hit mode=1, then N mode=0 calls, repeat.
Spacing 10^3 / 10^4 / 10^5 (11 hits) and 10^6 (7 hits).

Every finished threshold jettisons at hit **t+1**, independent of
spacing — including 10^6 warm calls between hits.

| t | first_reopt_hit (median, all spacings, 20/20) |
| --- | --- |
| 3 | 4 |
| 4 | 5 |
| 5 | 6 |
| 6 | 7 |
| baseline | none (11 ≪ 1000) |

At 10^6 the wall for 7 hits is ~15.7–15.9 ms: the DFG mode=0 path
stays useful until the jettison. Cost of the false jettison is one
DFG compile (~1 ms) plus backoff on the *next* real phase.

## 4. FTL A/B — identical corrected JS

Both logs: `compiling score with FTL` at line 70, `PHASE2_START` at
186, `warmup_done sawFTL=true retry=0`.

| | IC exits in phase2 | retry_after | phase_ms |
| --- | --- | --- | --- |
| baseline | 40 | 0 | 3.906 |
| candidate t=5 | 6 | 1 | 0.921 |

Excerpts: `matrices/closure-ftl-baseline.txt`,
`matrices/closure-ftl-candidate.txt`.

## 5. 64 cold sites — measured, not extrapolated

All 64 cold arms actually executed (1 hit each).

| | stubs | bytes total | bytes/stub | DFG compile |
| --- | --- | --- | --- | --- |
| baseline | 64 | 30720 | 480 (min=max) | 1.01 ms |
| candidate | 64 | 32768 | 512 (min=max) | 0.96 ms |

Delta: +32 B/stub, +2048 B (~6.7%). Compile time is noise.

## 6. Concurrent JIT

Poll `numberOfDFGCompiles(f) ≥ 1` (14645 calls) + 2000 settle, then
phase2. `retry 0 → 1`, rc=0. One successful run; not an EWS suite.

## 7. `codeTypeThresholdMultiplier()`

`CodeBlock.cpp` returns `evalThresholdMultiplier()` (default 10) for
EvalCode and 1 otherwise. The new helper uses the same product as
`exitCountThresholdForReoptimization()` and
`exitCountThresholdForReoptimizationFromLoop()`. Intentional: Eval
CodeBlocks are treated as less hot. No reason to diverge.

## 8. Conclusion on the cumulative counter

`m_count` is a good approximation of "this site became hot" for a
dense phase change. It is a poor approximation of a rate: any fixed
constant eventually jettisons a lifetime-rare site. That is a documented
limitation, not a reason to reject the design (baseline pays 1 exit per
rare hit forever; candidate pays 1 compile after t+1 such hits). A
decaying rate would be a redesign and is out of scope.

## 9. Threshold retained: 5

Conservative policy: largest threshold that keeps essentially all of
the durable phase-change benefit while cutting unnecessary jettisons.

- t=5 loses nothing measurable vs t=3 on case A.
- t=5 avoids E (5-then-never), 32×4, and the 4th/5th rare spaced hit.
- t=6 also avoids F / 32×5 / 6th rare hit, and A is still flat, but
  6 is the first value that refuses a 6-hit phase. Prefer 5.
- Not chosen because FromLoop is historically 5.
