# Adversarial FrozenMiniSearch / InadequateCoverage investigation

Primary verdict: **HISTORICAL 14.5% RESULT DOES NOT REPRODUCE**

This report does not invalidate the mechanical JSC issue. It rejects the
single-run 14.5% number as established normal-runtime performance evidence.

## Exact revisions and products

| Item | Revision |
| --- | --- |
| FrozenMiniSearch issue-4 base | `e07e4d98adfd7d4004c6df975ba3dab42e0292b6` |
| FMS PR #10 | `cb0b4d6ffad91f572f3469580bc22ae3afa91927` |
| FMS PR #12 | `70c786f7fc0f247beb504f8abd3f584de13bfbd9` |
| FMS PR #13 | `f9b7b8fbbc683170a30a969bca85d45c94ee3ffb` |
| WebKit candidate | `e01f57903d9e389b5651a167db7c519244f45842` |
| Candidate base | `f05fd6d8b3bee9719437f45a7cb1d1d7ee9c3151` |
| WebKit upstream at final refresh | `aca22be814e23246ea548d231fdb1defb7ee535f` |

The four policy files relevant to this patch are unchanged between the
candidate base and the refreshed upstream tip.

Local runtime: Bun `1.4.1-canary.1+11fb73032`, the exact PR #12 revision;
standalone JSCOnly Release built by clang 18.1.3 + libc++ on 4 x86-64 CPUs.
The randomized Bun replication was also repeated on a fresh GitHub
`ubuntu-24.04` runner with the same Bun revision.

Patched `jsc` SHA-256: `8a4c17a82fe8fb3440ac989d235ac043a7a7cda014f093e70170fc21db143484`.
Patched `libJavaScriptCore`: `7b70b401f04ee92f82323522305e5fb2ca5d15dd8c48234b639e6ae865031cbb`.

Exact generated workload:
`benchmarks/tmp/engines/issue4-multi-only.js`, SHA-256
`aa36b88cf62c0a8be2bae0fd69a480d57ef4e053af1a89160e10c4607d1e6eb4`.
Every run produced fingerprint `0ebf5d2b`.

## Historical evidence audit

| Experiment | Source / flags | Result | Strength | Does not prove |
| --- | --- | --- | --- | --- |
| Bun #40477 minimal diagnostic | dependency-free `scorePostingDoc`; FTL off, concurrent off, OSR tracing; global 100/1/1000 | 101/2/1001 same-site IC exits | Strong mechanics | Normal-runtime speedup |
| Bun #40477 minimal normal runtime | same source; normal FTL/concurrent; five processes | 4.53 ms default vs 4.70 ms global=1 | Useful negative | Real FMS trajectory |
| PR #10 accumulator helper | asserted source transform; FTL/concurrent off + tracing | scorer IC moved into helper; helper 101→2 | Strong localization | Normal source or normal-runtime A/B |
| PR #12 | **no source transform**; normal Bun; only global threshold; 3 fresh processes per condition | 4255.36→3639.15 us (−14.5%) | Relevant but weak sample | Reproducibility: conditions were blocked, default first, on one runner |
| PR #13 | asserted source transform; normal benchmark only at default; threshold comparison used FTL/concurrent off + tracing | scorer IC absent; traced 5250→4113 us | Strong diagnostic discriminator | Normal-runtime default-vs-G1 effect |
| WebKit closure | exact minimal Bun repro; same patched binary t=5 vs disabled; normal JSC | 101→6 mechanically, no robust wall-time gain | Strong same-binary negative | Real FMS workload |

Specific historical confounds:

- PR #12 used 3 samples, all default samples before all G1 samples.
- PR #12 was one GitHub runner. Its absolute median was ~4.3 ms; the same
  bundle/runtime here is ~2.6 ms.
- PR #10/#13 threshold timing numbers mix source transforms with DFG-only,
  no-concurrent, heavily traced execution.
- PR #13 never performed the missing normal-runtime threshold comparison.
- Diagnostic thresholds alter one option, but diagnostics also alter FTL,
  concurrency and logging; they establish mechanism, not mediation.

## Phase 2: faithful PR #12 reproduction

Command:

```sh
python3 run-fms-real-workload.py \
  --mode bun --executable "$(command -v bun)" \
  --bundle benchmarks/tmp/engines/issue4-multi-only.js \
  --repetitions 30
```

Each repetition shuffled default/G1 order.

| Bun condition | n | median us | p25 / p75 | p90 / p95 | bootstrap median CI95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| default | 30 | 2631.91 | 2546.92 / 2671.36 | 2758.59 / 2775.45 | 2559.41–2653.19 |
| global=1 | 30 | 2591.57 | 2550.27 / 2672.78 | 2854.20 / 3038.30 | 2561.81–2639.34 |

Delta: **−1.53%**, Mann–Whitney two-sided **p=0.712**.

The exact historical 3+3 blocked protocol was then repeated ten times,
alternating block direction. Median trial delta was **+1.22%** (G1 slower);
individual trial deltas ranged **−3.59% to +5.52%**. No trial approached
−14.5%.

Fresh GitHub runner replication:

| Condition | n | median us | p25 / p75 | p90 / p95 |
| --- | ---: | ---: | ---: | ---: |
| default | 30 | 2917.88 | 2861.01 / 3081.45 | 3398.43 / 3486.93 |
| global=1 | 30 | 2891.26 | 2828.18 / 2940.35 | 3025.28 / 3105.05 |

Delta **−0.91%**, p=**0.183**. Run:
https://github.com/yoch/WebKit/actions/runs/32903939788/job/97983686168

Therefore the historical effect failed both a stronger interleaved protocol
on two machines and repeated execution of its original weak protocol.

## Phase 3: decisive same-binary real-workload experiment

Same patched JSC binary and exact unmodified generated workload, 30
interleaved independent processes per condition:

- P0: global=100, per-site=1,000,000
- P5: global=100, per-site=5
- G1: global=1, per-site=1,000,000
- G1P5: global=1, per-site=5

| Condition | median us | p25 / p75 | p90 / p95 | bootstrap median CI95 | vs P0 |
| --- | ---: | ---: | ---: | ---: | ---: |
| P0 | 2328.96 | 2290.00 / 2369.31 | 2505.86 / 2643.36 | 2299.46–2345.33 | — |
| P5 | 2340.00 | 2306.29 / 2469.38 | 2595.40 / 2619.73 | 2316.21–2444.37 | +0.47%, p=0.183 |
| G1 | 2339.29 | 2309.08 / 2384.34 | 2583.29 / 2615.91 | 2321.00–2363.12 | +0.44%, p=0.559 |
| G1P5 | 2371.81 | 2302.50 / 2404.69 | 2483.45 / 2590.33 | 2308.63–2393.61 | +1.84%, p=0.322 |

P5 captures **none** of a 5–15% effect. More importantly, G1 itself captures
none on the exact workload under standalone JSC.

## Phase 4: transition versus settled code

The generated bundle was modified only in the outer measurement harness.
No product or hot function was instrumented. Twenty interleaved processes
per condition:

| Stage (median us) | P0 | P5 | G1 | G1P5 |
| --- | ---: | ---: | ---: | ---: |
| search 1 | 4250 | 4160 | 4140 | 4230 |
| search 2 | 3540 | 3440 | 3640 | 3640 |
| searches 3–4 | 3615 | 3605 | 3495 | 3430 |
| searches 5–8 | 3813 | 3433 | 3353 | 3335 |
| searches 9–16 | 3389 | 3204 | 3304 | 3386 |
| searches 17–32 | 3005 | 3027 | 2733 | 2834 |
| calibrated settled | 2393 | 2425 | 2380 | 2364 |

All policies converge. There is an ordinary warmup curve, but no stable P5
or G1 separation. This supports neither H1 nor H2 as a material 14.5% effect
on this machine; any early differences are small and noisy.

## Phase 5: diagnostic trajectory (separate, traced execution)

DFG-only/no-concurrent tracing of the real workload:

| | total exits | IC exits | scorer IC | scorer DFG compiles |
| --- | ---: | ---: | ---: | ---: |
| P0 | 2130 | 444 | 101 at bc#331 | 5 |
| P5 | 1082 | 77 | 6 at bc#331 | 5 |
| G1 | 99 | 23 | 2 at bc#331 | 5 |

P5 does recompile every repeated `InadequateCoverage` site earlier, not only
the scorer. G1 additionally truncates non-IC trajectories:

- scorer `BadIdent`: P0/P5 400, G1 4;
- scorer `BadConstantValue`: P0/P5 201, G1 3;
- many `BadCache` sequences are similarly shortened.

Thus G1 causes additional recompilation events that P5 intentionally does
not. But those differences do not mediate a measurable normal-runtime gain
in the reproduced workload. Compilation counts for the requested focus
functions were unchanged: scorer 5 DFG compiles, aggregate 1,
`executeQuerySpecInternal` 1.

## Phase 6: PR #13 missing normal-runtime discriminator

Exact PR #13 transform, same fingerprint, 30 interleaved Bun processes:

| Specialized condition | median us | p25 / p75 | CI95 |
| --- | ---: | ---: | ---: |
| default | 2700.53 | 2621.18 / 2821.10 | 2652.10–2783.65 |
| global=1 | 2661.09 | 2543.43 / 2784.43 | 2599.05–2728.52 |

Delta **−1.46%**, p=**0.243**: no normal-runtime effect.

Separate diagnostics confirmed zero `InadequateCoverage` exits in both
`scorePostingDoc` and `scorePostingDocNew`. Other IC sites remained
(343 default, 21 G1), notably `collectDirectGroups` (201 default). The
specialization therefore removed the original scorer IC rather than merely
renaming it, while global=1 still changed many diagnostic exits. It still
did not improve normal runtime.

## Reconciliation

There is no longer a robust conflict to reconcile:

1. The mechanical fact is real: default 101, P5 6, disabled 101.
2. The tiny standalone repro correctly showed no normal-runtime win.
3. The real FMS workload also shows no reproducible normal-runtime win from
   either P5 or G1 under stronger protocols.
4. The historical 14.5% sample was a single blocked 3+3 runner observation.
   It is retained as an anomalous result, not treated as causal evidence.

The diagnostic trajectory explains why intuition was tempting: G1 changes
many more exit kinds than P5. The clean performance experiments show those
changes do not yield a stable latency benefit here.

## Falsification and recommendation

Strongest competing interpretation: “the global speedup is real but P5
misses other important exits.” It is falsified in this environment by the
30-process G1-vs-P0 comparison (**+0.44%, p=0.559**) and by the exact Bun
PR #12 replication (**−1.53%, p=0.712**).

Recommendation: **do not prepare/rebase an upstream candidate on performance
grounds**. Keep PR #5 parked as a mechanically valid heuristic prototype.
No threshold tuning is justified. The existing sparse rare-hit adverse case
also remains: cumulative per-site counts eventually fire at spacings
10^3–10^6.

Raw samples and compact diagnostic timelines:
`matrices/fms-adversarial-evidence.json`.
