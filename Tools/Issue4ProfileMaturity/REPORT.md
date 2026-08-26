# FrozenMiniSearch issue #4 / JSC profile maturity

Research branch: `cursor/jsc-profile-maturity-91da`
Fork PR: https://github.com/yoch/WebKit/pull/6
Date: 2026-08-26

This is **not** a product patch. No upstream WebKit PR. No Bugzilla.

Goal: answer two questions together enough to test a connection, without
forcing one:

1. Why Node/V8 becomes substantially faster than Bun/JSC on
   FrozenMiniSearch's history-sensitive multi-term workload, while Bun/JSC
   stays faster on simpler workloads.
2. After InadequateCoverage / ForceOSRExit, is there a principled
   profile-maturity recovery for JSC, and would it also explain (1)?

## Verdict

**E. `V8 HISTORY EFFECT IS THE PRIMARY PHENOMENON; JSC ISSUE IS SECONDARY`**

The crossover (Node faster than Bun on multi after other queries; Bun
faster on isolated multi) is a V8 allocation-site pretenuring lock-in.
It reproduces in d8. Disabling pretenuring removes the ~2× Node unlock
and leaves Bun faster.

JSC InadequateCoverage is real and independently reproduced. On this
workload it is **not** the cause of the V8 advantage, and making JSC
reoptimize earlier makes the real full-history multi **worse**. A
coverage-aware “wait for the new profile, then recompile” policy is
already approximated by the current 100-exit budget; after that wait
the recompiled `scorePostingDoc` still fails to reach the isolated-multi
FTL machine code.

### Strongest falsifier

If `--no-allocation-site-pretenuring` still produced Node B-M ≈ 2×
faster than Node M **and** Node B-M faster than Bun B-M, E would be
false. That experiment was run at n=30: B-M vs M is +0.33%, p=0.91;
Node B-M median 3605 µs vs Bun B-M 2331 µs. Bun still wins.

A second prospective falsifier: a JSC-only change that makes FULL/BSM
multi ~2× faster than isolated M without changing V8. CURRENT vs
OLD-EARLY vs NEVER-REOPT all fail that test.

---

## 1. Exact environment

See `ENVIRONMENT.md`. Short form:

- WebKit source notes SHA: `cab391584f801d18cde18093204d9b980964ca80`
- Unpatched `jsc` used for timing: lib SHA-256 `c54efc16…abd6642b1`,
  built 2026-08-25 from `3a999a1a45ed` (Release, clang-18, libc++)
- FrozenMiniSearch: `e07e4d98adfd7d4004c6df975ba3dab42e0292b6`
- Node 26.7.0 / V8 `14.6.202.34-node.28`
- d8 V8 15.4.61
- Bun `1.4.1-canary.1+11fb73032`
- Intel Xeon, 4 cores, Linux 6.12, Ubuntu 24.04
- Fingerprint `0ebf5d2b` on every successful multi sample

Fork `origin/main` (`5549b366`) is **behind** upstream; this branch
starts from upstream `main`, not the fork default.

---

## 2. Evidence matrix

Method for all FMS latency cells unless noted: fresh process per sample,
labels shuffled inside each repetition, Mann–Whitney two-sided, fingerprint
preserved. Scripts: `scripts/make-history-bundle.py`,
`scripts/run-history-matrix.py`. Raw JSON under `matrices/`.

| Claim | Experiment | Result | Confidence | Not eliminated |
| --- | --- | --- | --- | --- |
| Isolated multi: Bun/JSC faster than Node | Node/Bun/jsc M, n=30 | Node 3798 µs; Bun 2419; jsc 2283 | high | machine-specific constants |
| After any other complete query, Node ~2× | Node BM/SM/FM/BSM/SBM/FULL vs M, n=30 | −48.5% to −49.5%, U=0, p≈3e-11 | high | Maglev inlining of a one-off brand into `main` (sites would then not be `scorePostingDoc`'s) |
| Extra multi does **not** reach the fast Node state | Node MM vs M, n=30 | −14.5% only (3247 vs 3798) | high | Maglev/TurboFan contribution to the leftover 14% |
| Minimal V8 prefix is **one** other complete query | BM ≡ SM ≡ FM ≡ FULL on Node | all ≈1920 µs | high | a smaller-than-one-search brand invocation that is **not** inlined (prior work; not re-run here) |
| V8 unlock is allocation-site pretenuring | Node `--no-allocation-site-pretenuring` M vs BM, n=30 | +0.33%, p=0.91 | high | MM still −11% without pretenuring (second effect) |
| Engine-level, not Node embedder | d8 15.4 M vs BM, n=30 | −34.8%, U=0 | high | Node vs d8 magnitude (49% vs 35%) |
| Bun does not get a 2× unlock | Bun n=30 | single prefix 0 to −4%; BSM/FULL **+5%** | high | embedder vs JSC split of the +5% |
| JSC FULL is slower, not faster | jsc CURRENT n=30 | BSM +12.5%, FULL +14.1%; BM +1.2% ns | high | GC/RSS residual vs compile-quality |
| IC appears on one prefix without the 14% hit | jsc BM OSR dump vs latency | BM has `InadequateCoverage` 201+101+101 on query helpers; latency ≈ M | high | dump is one traced process |
| Early reopt is worse on FULL | `--osrExitCountForReoptimization=1` n=20 | FULL +28.4% vs M | high | not identical to parked per-site=5, but same direction as prior P5 |
| Never-reopt removes FULL-vs-M gap but slows M | threshold=1e6 n=20 | FULL −0.86% ns vs M; M 2651 vs CURRENT M 2283 | high | other exits (BadIdent/BadCache) also suppressed |
| Coverage-aware wait is not the missing piece | source + CURRENT already waits ~100 IC exits; FULL first DFG of `scorePostingDoc` already delayed for liveness 0.38 | later DFG size matches isolated M (5632B) but FULL never emits FTL 5184B | medium | one traced FULL process; FTL may finish after the measured window |
| RSS is not the independent variable | prior issue-4 restart + this history matrix | same multi fingerprint; history not working-set size | high | GC as **mediator** of V8 pretenuring (yes) vs RSS threshold (no) |

---

## 3. Minimal history prefix that flips V8

**One complete other search in the same process**, invoked through the
same `runSearch` / `scorePostingDoc` sites as the measured multi.

| History | Node median µs (n=30) | vs M |
| --- | ---: | ---: |
| M (multi only) | 3798 | — |
| MM (many extra multi) | 3247 | −14.5% |
| B-M | 1927 | **−49.3%** |
| S-M | 1932 | −49.1% |
| F-M | 1958 | −48.5% |
| B-S-M | 1922 | −49.4% |
| S-B-M | 1919 | −49.5% |
| FULL-M | 1919 | −49.5% |

Brand (`doliprane`, 5762 hits, no AND), substance, and fuzzy all suffice.
Permutations do not matter. Extra copies of **multi** do not.

That matches the object-survival story: brand/substance/fuzzy keep almost
every `scorePostingDoc` temporary alive as a result; multi's AND deletes
most of them (464 final hits).

---

## 4. V8 slow vs fast: distinguishing event

Not “both end optimized.” The accepted chain is:

```
brand / substance / fuzzy
  → every posting becomes a live result (no AND)
  → allocation sites in scorePostingDoc's else-branch see survival ≈ 1.0
  → V8 locks those sites TENURE (threshold 0.85, sticky)

isolated multi
  → combinators[AND] does a.delete(docId) for docs missing a term
  → the same sites see survival ≈ 0.38–0.50
  → V8 locks those sites DON'T TENURE

later multi:
  TENURE        → short-lived AND objects allocated in old space
                  → few nursery scavenges on the measured query
                  → ~1.9 ms
  DON'T TENURE  → same objects stay in the nursery
                  → scavenges dominate
                  → ~3.8 ms
```

The four sites are the literals in `src/scoring.ts` `scorePostingDoc`
when inserting a new doc (`{score, terms, match}`, `[sourceTerm]`,
`{ [derived]: [field] }`, `[field]`). A fifth site (464 survivors) is
the finalized `SearchResult` object; it tenures in **both** histories
and does not distinguish them.

Fresh diagnostic traces (not timing evidence; raw in
`matrices/v8-M-pretenure-gc.txt` and `v8-BM-pretenure-gc.txt`):

Isolated multi, first search-phase scavenge:

| site | created, found, ratio | decision |
| --- | --- | --- |
| 4× `scorePostingDoc` | 3930, 1489, **0.379** (one site 0.497) | undecided ⇒ **don't tenure** |
| 1× finalize | 440, 440, 1.000 | undecided ⇒ tenure |

Brand then multi. Brand's first search-phase scavenge:

| site | created, found, ratio | decision |
| --- | --- | --- |
| 4× `scorePostingDoc` | 3053–4840, same, **1.000** | undecided ⇒ **tenure** |

Then during multi, those same four sites show survival **0.11–0.14**
but stay `tenure => tenure`. Sticky. AND is now killing temporaries;
V8 does not reverse the brand decision. One additional multi-only site
locks `don't tenure` at 6827/464 = 0.068 (does not undo the four).

`--trace-pretenuring-statistics` prints `threshold=0.85`.

Caveat: Maglev OSR can inline `scorePostingDoc` into `main`. Then
survivors attach to `main`'s sites and a later multi still hits
undecided `scorePostingDoc` sites and locks don't-tenure. That is why
`runSearch(brand)` from `main` in a hot loop does **not** unlock, while
one non-inlined `runSearch` through the shared function does.

Causal ablation (this session, n=30, interleaved):

| Node 26.7.0 | M | BM | BM vs M |
| --- | ---: | ---: | ---: |
| default | 3798 | 1927 | **−49.3%** |
| `--no-allocation-site-pretenuring` | 3593 | 3605 | **+0.33% (ns)** |

d8 15.4 reproduces BM −34.8% vs M (engine-level).

Secondary leftover: MM is still −11% with pretenuring off. That is
**not** the crossover. Hypothesis: ordinary warmup / IC / inlining.
Not diagnosed further; it does not make Node beat Bun.

Prior CPU profiles (cited, not re-taken): AND and finalize look ~5×
slower on cold multi because they run under nursery scavenges, not
because the combinator was trained on the wrong query. `--no-turbofan`
and `--no-maglev` previously left the gap; `--no-use-ic` destroyed both
paths equally.

Competing JIT-graph explanation is **not** eliminated for the leftover
MM −11%. It **is** eliminated as the cause of the 2× unlock.

---

## 5. JSC isolated vs full-history optimization timeline

Source facts (upstream `cab391584f80`; citations in
`JSC-SOURCE-NOTES.md`):

- `DFGByteCodeParser::getPrediction()` inserts `ForceOSRExit` on
  `SpecNone` (`DFGByteCodeParser.cpp` 1322–1332). Intentional.
- Lowered to OSR kind `InadequateCoverage`.
- `handleExitCounts` uses `osrExitCountForReoptimization=100` unless an
  inlined frame has `DidTryToEnterInLoop` (then 5).
- `shouldOptimizeNowFromBaseline` gates **first** DFG on liveness 0.75 /
  fullness 0.35, with `maximumOptimizationDelay=5`. It is **not**
  re-applied to “the SpecNone bytecode that just caused IC”.
- No IC-specific threshold on this tree.

Performance (`matrices/history-jsc.json`, unpatched, n=30):

| History | median µs | vs M |
| --- | ---: | ---: |
| M | 2283 | — |
| BM | 2310 | +1.2% ns |
| BSM | 2568 | +12.5% |
| FULL | 2605 | +14.1% |

Compile/OSR dumps are **diagnostic**, not timing evidence
(`matrices/jsc-timeline.json`).

### `scorePostingDoc` machine-code sequence

| History | sequence (tier / bytes) | InadequateCoverage |
| --- | --- | --- |
| M | Baseline 6912 → DFG 5632 ×4 → **FTL 5184** | **0** (BadIdent 801, BadCache 401, BadConstantValue 101) |
| BM | Baseline 6912 → DFG 3840 → DFG 4096 → FTL 3456 → DFG 5376 ×4 → DFG 5632 → **FTL 5184** | 201 at bc#430 |
| BSM | … FTL 3456 then many DFG 5376 … last DFG **5888**, no FTL 5184 in dump | (verboseOSR, no per-exit) |
| FULL | same early FTL 3456; 15 compiles; last DFG **5632**; **only FTL is 3456** | (verboseOSR, no per-exit) |

BM also: `combineResults` IC 101 bc#192, `useGatedEvaluation` IC 101
bc#18, `collectDirectGroups` IC 101 bc#56.

### First DFG of `scorePostingDoc` under FULL

`--verboseOSR` on FULL:

```
Profile hotness: 0.384615 (10 / 26), 0.627907 (27 / 26)
Delaying optimization ... because of insufficient profiling.
```

Liveness 0.38 < 0.75. After `maximumOptimizationDelay=5` it compiles
anyway → DFG **3840B** (brand-shaped; AND bytecode still `SpecNone`).
That is the existing maturity gate **forcing a compile with incomplete
coverage**, then ForceOSRExit when multi activates the AND path.

Later DFGs grow to 5632B (same as isolated M). Isolated M then FTLs to
5184B. FULL, in the dump of a complete benchmark process, never does.
Retry counters on M `scorePostingDoc` reached 2–3; BM 0/1/3. FULL
`--verboseOSR` does not print `reoptimizationRetryCounter` on every
optimize-now (that field is on OSR-exit lines).

### Does full-history compile with more incomplete profile?

**Yes, at first DFG of `scorePostingDoc`.** Diversified execution
(brand) leaves 16/26 value profiles dead. Isolated multi profiles the
AND path before the first DFG. After ~100 IC exits the profiles fill
(DFG size matches M); the remaining damage is **reoptimization churn /
failure to reach FTL 5184**, not “we recompiled before any samples.”

Compile counts (diagnostic):

| | Baseline | DFG | FTL | total |
| --- | ---: | ---: | ---: | ---: |
| M | 112 | 109 | 45 | 267 |
| BM | 116 | 130 | 53 | 300 |
| BSM | 119 | 141 | 56 | 318 |
| FULL | 124 | 155 | 60 | 341 |

More history → more DFG compiles. Not more useful FTL for
`scorePostingDoc`.

---

## 6. CURRENT vs OLD-EARLY vs COVERAGE-AWARE

No source patch on this branch. Policies were discriminated with
existing `osrExitCountForReoptimization` on the same unpatched binary.

| Policy | flag | M median | BM vs M | FULL vs M |
| --- | --- | ---: | ---: | ---: |
| CURRENT | default 100 | 2283 (n=30) | +1.2% ns | **+14.1%** |
| OLD-EARLY (global) | `=1` | 2242 (n=20) | +2.8% | **+28.4%** |
| NEVER-REOPT | `=1000000` | 2651 (n=20) | +8.3% | **−0.86% ns** |

A site-specific coverage-aware prototype was **not** written. Reasons:

1. CURRENT already waits ~100 baseline trips on a deterministic
   ForceOSRExit before jettison — that *is* a coverage wait.
2. OLD-EARLY (recompile sooner) **doubles** the FULL penalty.
3. After that wait, FULL's `scorePostingDoc` DFG size already matches
   isolated M; the missing piece is FTL 5184, not more samples.
4. NEVER-REOPT equalizes FULL and M by **also making isolated M 16%
   slower** (BadIdent/BadCache reopt is useful on M).

The parked per-site IC=5 candidate is OLD-EARLY in spirit. Prior
session: P5 made FULL +14% vs unpatched FULL. Same sign as G1 here.

Coverage-aware hypothesis **fails** as an explanation of the V8
crossover and **fails** as a better FMS policy under these approximations.

Adversarial 6-exits-in-20-calls vs 6-exits-in-10M-calls: not run as
synthetics. FMS already supplies the important pair: BM (IC present,
latency OK because FTL 5184 is reached) vs FULL (more compiles, no FTL
5184, +14%). A recency heuristic that treated those the same would be
wrong; they are not the same.

---

## 7. FrozenMiniSearch real-workload performance

Cross-engine, same bundles, interleaved, fingerprint `0ebf5d2b`.

Isolated multi (M):

| runtime | n | median µs |
| --- | ---: | ---: |
| Node 26.7.0 | 30 | 3798 |
| d8 15.4 | 30 | 2389 |
| Bun 1.4.1 | 30 | 2419 |
| jsc CURRENT | 30 | **2283** |

Full history (FULL) / B-M:

| runtime | B-M | FULL | vs own M |
| --- | ---: | ---: | ---: |
| Node | 1927 | 1919 | **−49%** |
| d8 | 1557 | (not run) | −35% (BM) |
| Bun | 2331 | 2546 | BM −3.6%; FULL **+5.3%** |
| jsc CURRENT | 2310 | 2605 | BM ns; FULL **+14.1%** |

Crossover arithmetic on this machine:

- Isolated: jsc 2283 vs Node 3798 → **JSC 1.66× faster**
- After brand: Node 1927 vs Bun 2331 vs jsc 2310 → **Node fastest**
- After FULL: Node 1919 vs Bun 2546 vs jsc 2605 → **Node ~1.36× Bun**

No JSC policy in §6 approaches Node's FULL 1919 µs. NEVER-REOPT FULL is
2628 µs.

Brand / substance / fuzzy Node cells are in `matrices/history-node.json`
(all ~1920 after prefix). Bun single-prefix cells stay within 4% of M.

---

## 8. Selected WebKit benchmarks

**Not run.** Justification: this investigation does not propose a JSC
source change. ARES-6 / JetStream2 would measure an unpatched engine
against itself. Prior parking of the IC=5 candidate was already based on
the real FMS FULL regression, which this session reproduced (G1 FULL
+28%).

If a future JSC patch is revived, the relevant existing harnesses are:

- `PerformanceTests/ARES-6/cli.js` — isolated global, hundreds of
  iterations, long-lived optimized functions (phase / tiering).
- `PerformanceTests/JetStream2/cli.js` — multi-phase, d8/sm/jsc CLI.
- `JSTests/microbenchmarks/` for a later ForceOSRExit micro if a patch
  exists.

Running them now would add noise, not a decision.

---

## 9. Adversarial cases

Synthetic micros (abrupt phase, rare spaced path, oscillation, many
cold sites, stable, progressive poly, callback identity) were **not**
re-implemented on this branch. The parked candidate already had those
on `cursor/jsc-inadequate-coverage-v2-91da`; they looked “pretty” and
still lost on FMS FULL.

This session used the real FMS histories as the adversarial matrix:

| Case | FMS stand-in | CURRENT result |
| --- | --- | --- |
| No phase change | M | fastest JSC (2283); FTL 5184 |
| Abrupt permanent phase | BM (brand then multi) | IC appears; latency ≈ M; FTL 5184 recovered |
| Diversified then measured | BSM / FULL | +12–14%; FTL 5184 **not** recovered in dumps |
| Same-query warmup | MM | Node −14%; Bun −3%; not a 2× |
| Early reopt on phase change | G1 FULL | **+28%** |
| Never reopt | noreopt FULL | gap vs M disappears; M itself +16% vs CURRENT |

Rare-spaced IC (1 per 1e6) was the parked patch's intended win vs a
global threshold. It is irrelevant to FMS: the newly uncovered AND path
is **hot**, not rare.

---

## 10. Recommendation

**No JSC patch.** Keep the per-site InadequateCoverage candidate parked.

**Do not file Bugzilla** from this work (instruction). If something is
filed later, they are **separate**:

- V8: sticky allocation-site pretenuring interacting with AND that
  kills temporaries. Likely **intended**. Product note, not a V8 bug.
- JSC: ForceOSRExit on SpecNone is **sound**. The FMS FULL penalty is
  reoptimization churn after a first DFG that was forced through with
  liveness 0.38, then failure to reach the isolated-multi FTL. That is
  a possible future JSC research topic; it is not a 5-exit heuristic.

**FrozenMiniSearch product workaround** (if Node/V8 history dependence
is unwanted):

- For **history-independent** numbers: run with
  `--no-allocation-site-pretenuring`, or measure multi in a fresh
  process.
- For **fast Node** in a long-lived process: run one high-survival
  query (`doliprane` / `paracetamol`) through `runSearch` **before**
  measuring multi, without Maglev-inlining that query into `main`.

**Continue research** only if the JSC FTL-starvation story is the
goal — not to chase the V8 2×. A next JSC experiment would be: dump
`reoptimizationRetryCounter` + FTL threshold on `scorePostingDoc` at
every jettison under M vs FULL, in a **non-timed** process, and test
whether resetting retry on “profile set changed” lets FULL emit FTL
5184 without bringing back G1's +28%. That is still not a patch.

Connection verdict between the two questions: **C in the brief's A/B/C
split** (unrelated mechanisms, same workload). Mapped to the required
one-letter scale: **E**.

---

## Answers to the brief's numbered JSC questions

1. **Can the SpecNone origin be associated with the OSR exit?** Cheaply
   today: the exit already has `bc#` in the OSR record
   (`scorePostingDoc` bc#430, `combineResults` bc#192, …). The CodeBlock
   does not store “this bytecode was the reason for ForceOSRExit” as a
   first-class maturity wait. Adding that is possible; it was not shown
   to be profitable.

2. **After the first IC exit, how quickly does the profile fill?** On
   BM, 101 IC exits on `combineResults` / `useGatedEvaluation` match the
   generic budget; `scorePostingDoc` 201 suggests two reopt cycles.
   Later DFG size 5632B = isolated M, so the profile **does** fill
   during those ~100 baseline trips.

3. **Does JSC retry optimization before the new profile is
   representative?** First DFG of FULL `scorePostingDoc`: **yes**,
   via `maximumOptimizationDelay=5` with liveness 0.38. After IC:
   CURRENT waits ~100, which is representative enough for DFG size, not
   for a stable FTL.

4–6. See §5. FULL has more DFG compiles, a smaller first DFG, IC on
   AND-related helpers, and no final FTL 5184 in the dump. Isolated M
   has no IC on `scorePostingDoc` and does reach FTL 5184.

---

## What was destroyed

- “101 IC exits looks bad, therefore recompile immediately is better.”
  Destroyed by G1 FULL +28% and parked P5.
- “Wait for the newly needed profile, then recompile” as the V8-crossover
  fix. Destroyed: V8 is pretenuring; CURRENT already waits; DFG size
  matches; FULL still slower.
- “JSC profile maturity explains a material part of Node beating Bun.”
  Destroyed: no-pretenuring Node stays ~3600 µs; Bun BM ~2330 µs.
- “Memory residency is the independent variable.” Destroyed earlier;
  this history matrix agrees.

What remains real: ForceOSRExit is doing what it was written to do;
FULL JSC is ~14% slower than isolated JSC for a **different** reason
than V8's 2×; that JSC reason is not a candidate for the old threshold
patch.
