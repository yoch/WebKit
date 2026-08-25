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
addition to any bulk warmup. `--trace-deopt` shows no deopt loop, and the
gap **survives `--no-turbofan` and `--no-maglev`**. The degraded state is
therefore not a bad TurboFan compile. See §3.1.

## 3.1 V8 mechanism: allocation-site pretenuring lock-in

Result cardinalities on this corpus (concatenated across the 3 target
indexes):

| query | results | terms/result | uses `combinators[AND]`? |
| --- | ---: | ---: | --- |
| brand `doliprane` | **5762** | 1 | no (single spec) |
| substance `paracetamol` | 4609 | 1 | no |
| fuzzy `paracetmol` | 4609 | 1 | no |
| multi `amoxicilline 500` | **464** | 2 | **yes** (gated AND) |

Brand never executes the AND combinator. It still unlocks multi because
brand and multi share the object-literal allocation sites in
`scorePostingDoc` / `finalizeSearchResults`.

V8 tracks each bytecode allocation site and, after a scavenge, looks at
the fraction of objects from that site that survived (`--trace-pretenuring-statistics`,
threshold 0.85). Once a site is classified it **does not go back**.

Cold multi, first search-phase scavenges:

```
(4947 created, 1369 survived, ratio 0.277)  undecided => don't tenure   ×4 sites
(440, 440, 1.000)                           undecided => tenure         ×1 site
```

AND deletes most `scorePostingDoc` temporaries before the search returns,
so those sites lock in **don't tenure**. Later multi iterations stay in
the nursery; scavenges dominate. The one tenured site is the 464 final
result objects.

Brand-first, first search-phase scavenges:

```
(5738, 5738, 1.000)  undecided => tenure   ×4 sites
```

Every posting becomes a surviving result (no AND). The same four sites
lock in **tenure**. Multi then allocates its short-lived AND temporaries
straight into old space (`(4293, 464, ratio 0.108) tenure => tenure` —
already tenured, not reconsidered). Nursery pressure collapses.

Causal flag, n=6:

| | Node multi median us |
| --- | ---: |
| default, multi-only | ~3800 |
| default, after brand | ~1950 |
| `--no-allocation-site-pretenuring`, multi-only | 3594–3719 |
| `--no-allocation-site-pretenuring`, after brand | 3587–3832 |

The 2× gap **disappears** when pretenuring is disabled. `--no-use-ic`
makes both ~18 ms (ICs are required for the fast path, but do not
*differentiate* the two histories). `--no-inline-new` makes the unlocked
path *slower* than cold (9300 vs 7400), consistent with old-space
free-list allocation without the inline bump path.

This also explains the previously puzzling negatives:

- 1–4096 `consume(runSearch(brand))` in a hot loop in `main` does **not**
  unlock: Maglev/OSR inlines `scorePostingDoc` into `main`, so the
  surviving allocations attach to `main`'s sites, not to the shared
  function. Multi then hits still-undecided `scorePostingDoc` sites and
  locks in don't-tenure.
- `measureSearch(brand)` alone does **not** unlock for the same inlining
  reason (sites land in `measureSearch`).
- `fingerprint(brand())` from `main` (one non-inlined call) plus any
  bulk warmup **does** unlock: the 5762 live objects are attributed to
  `scorePostingDoc`'s own sites.
- 512 extra multi iterations never recover: the don't-tenure decision is
  already sticky, and AND keeps the survival ratio ~0.28–0.50, below 0.85.

CPU profiles of the multi phase remain compatible with this (AND and
finalize look 5× slower because they run under nursery scavenges and
un-pretentured allocation, not because AND was trained on a different
query):

| function | cold multi (us/search) | unlocked (us/search) | ratio |
| --- | ---: | ---: | ---: |
| `combinators[AND]` | 661 | 136 | 4.9x |
| `finalizeSearchResults` | 465 | 93 | 5.0x |
| GC | 1232 | 709 | 1.7x |
| `scorePostingDoc` | 790 | 578 | 1.4x |

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
2. **Which phase?** On the V8 side the apparent 5× AND / finalize
   penalty is a *consequence* of allocation-site pretenuring, not a
   combinator trained on the wrong query. Brand (5762 survivors, no AND)
   pretentures the shared `scorePostingDoc` literals; multi alone
   (survival ~0.28 because AND deletes temporaries) locks the same sites
   as don't-tenure. Fingerprints are identical; the work is the same.
3. **Is GC involved?** Yes, as the *mediator*, not as a threshold
   crossing during the measured query. `--no-allocation-site-pretenuring`
   equalizes Node at ~3650 µs. Inert allocation churn does not unlock
   because it does not go through those bytecode sites. A larger
   new-space (`--max-semi-space-size=128`) helps both sides ~15% and
   leaves the gap.
4. **Runtime vs engine?** Engine-level on both sides: reproduced in
   standalone JSC (pollution, threshold sensitivity) and in Node/V8
   (cold-start lock-in). Not a Bun/Node runtime-layer artifact.

## 6. Open follow-ups

- V8: the pretenuring lock-in is now identified. Remaining product
  question is whether FMS should stop mutating result objects after
  allocation (so AND temporaries are not the same literals as
  long-lived brand results), or whether the benchmark should not
  concatenate unrelated workloads in one process.
- JSC: still a different mechanism — cumulative type-feedback pollution
  on the shared functions. Early recompilation (P5/G1) makes that worse.
- Both engines leave real latency on the table on this workload: best
  observed multi is ~1600 us (pretentured V8) vs ~2200 us (JSC
  multi-only) vs ~2565–2900 us (JSC full profile).
