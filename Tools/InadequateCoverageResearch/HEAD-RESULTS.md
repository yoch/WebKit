# Pass 2 results on WebKit/WebKit `3a999a1a45ed`

Distinguish from pass 1 (`5549b366` / PRs #2/#3). JSC policy files were
identical between those SHAs; these numbers were re-measured on this HEAD.

## Rebase / baseline

| Item | Value |
| --- | --- |
| Upstream HEAD | `3a999a1a45ed3cf451677c24ee47f18bd3ce7e65` |
| Research branch | `cursor/jsc-inadequate-coverage-v2-91da` |
| Toolchain | Ubuntu clang 18.1.3 + libc++ (`-stdlib=libc++`) |
| Build | `build-webkit --jsc-only --release`, `makeargs=-j4 jsc` |
| Arch | x86_64 Linux only |
| Baseline libJavaScriptCore | sha256 `c54efc1645a0…6642b1` size 39134472 |
| Candidate lib (sweep, default 5) | sha256 `fca37adc0ad2…4420a` size 39134576 (+104 B) |
| Candidate lib (final, default **3**) | sha256 `4a292e19ecc8…6eb2a8` size 39134576 |
| Default confirmed | `jsc --dumpOptions=2` → `osrExitCountForReoptimizationFromInadequateCoverage=3` |
| Isolated baseline | `/tmp/ic-research-v2/baseline` (RPATH) |
| Isolated candidate | `/tmp/ic-research-v2/candidate` (RPATH) |

Raw machine-readable matrices:

- `Tools/InadequateCoverageResearch/results/v2-baseline-3a999a1a.tsv`
- `Tools/InadequateCoverageResearch/results/v2-candidate-3a999a1a.tsv`

(gitignored under `Tools/**/results`; copies live on the agent disk.)

## Per-site threshold matrix (candidate, global=1000)

Compare is `m_count > t` after increment: **t=0 first hit, t=1 second, t=3 fourth, t=5 sixth**.

`reopt` = retry counter incremented. `IC` = InadequateCoverage speculation failures.

| Case | t=0 | t=1 | t=2 | t=3 | t=5 | t=10 | baseline (no per-site) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A durable same-site 20k | reopt IC=3, 2.4ms | reopt IC=3, 2.4ms | reopt IC=4, 2.3ms | reopt IC=5, 2.6ms | reopt IC=7, 2.7ms | reopt IC=12, 3.4ms | reopt IC=1002, **84ms** |
| B exactly 1 then never | **reopt** | no | no | no | no | no | no IC=1 |
| C exactly 2 | **reopt** | **reopt** | no | no | no | no | no IC=2 |
| D exactly 3 | **reopt** | **reopt** | **reopt** | no | no | no | no IC=3 |
| E exactly 5 | **reopt** | **reopt** | **reopt** | **reopt** | no | no | no IC=5 |
| F exactly 6 | **reopt** | **reopt** | **reopt** | **reopt** | **reopt** | no | no IC=6 |
| G 32×1 | **reopt** | no IC=32 | no | no | no | no | no IC=32 |
| H 32×2 | **reopt** | **reopt** | no IC=64 | no | no | no | no IC=64 |
| I 32×3 | **reopt** | **reopt** | **reopt** | no IC=96 | no | no | no IC=96 |
| J 32×6 | **reopt** | **reopt** | **reopt** | **reopt** | **reopt** | no IC=192 | no IC=192 |
| K Zipf | reopt IC=2, 2.9ms | reopt 3.3ms | reopt 4.2ms | reopt 4.4ms | reopt 5.5ms | reopt 7.3ms | reopt IC=1002, 79ms |
| L 8×20 burst then gone | reopt retry=1 | same | same | same | same | same | no IC=160 |
| M 4 durable phases | reopt retry=4 IC=5, 5.5ms | retry=4 IC=20 | IC=35 | IC=50 | IC=80, 12.8ms | IC=155, 20ms | retry=3 IC=15004, **1220ms** |
| N short A/B | reopt retry=1 IC=2, 2.1ms | IC=4 | IC=6 | IC=8 | IC=12, 3.2ms | IC=22 | retry=1 IC=1002, 79ms |
| O long A/B 2k | reopt retry=2 IC=3, 2.9ms | IC=6 | IC=9 | IC=12 | IC=18, 4.2ms | IC=33 | retry=2 IC=3003, 231ms |

Backoff on M (t=5) is visible in per-site counts: 6, 11, 21, 41 (5→10→20→40). Same shape at every t.

## Why not 5? Why 3?

- **0, 1, 2 are rejected.** They jettison G/H/I (32 distinct sites ×1/×2/×3). That is a cold spray, not a phase change.
- **3 is the first value that survives G/H/I.** Adaptation on A is 2.6ms vs 84ms unpatched.
- **5 only additionally ignores E (exactly 5 then never).** Cost vs 3 on A is ~0.1ms. That is not a reason to prefer 5 over 3.
- **10** additionally ignores F and J, and slows M (20ms vs 13ms). Still fine on A, but it delays a real 6-hit phase.
- FromLoop's historical 5 is **not** a justification for reusing that number on a different policy.

Default proposed: **3**.

## Design A vs B

Coupling (40 same-site hits, global=1000):

| knobs | reopt | IC |
| --- | --- | --- |
| dedicated=5, FromLoop=100 | **yes** | 6 |
| dedicated=100, FromLoop=5 | **no** | 40 |
| dedicated=5, FromLoop=5 | yes | 6 |

Design A (reuse FromLoop) **fails the first row's intent**: raising FromLoop to 100 would silently disable the InadequateCoverage policy.

JSC already splits budgets: `osrExitCountForReoptimization` (100), `FromLoop` (5), `ftlOSREntryFailureCountForReoptimization` (15). A fourth dedicated option matches that convention. The option cost is one Unsigned + one CodeBlock helper.

**Choose Design B.**

## FTL proof (candidate, t=5, chronological merged stdio)

Log: `results/v2-candidate-3a999a1a-ftl-proof-t5.log`

1. `DFG(Driver) compiling score#… with FTL` (before phase change)
2. `Installing score#… FTLFunctionCall`
3. `FTL_PROOF warmup_done sawFTL=true … retry=0`
4. `FTL_PROOF PHASE2_START`
5. `Generated JIT code for FTL OSR exit #1 (… bc#55, InadequateCoverage) from score#… FTLFunctionCall`
6. `Speculation failure in score#… FTLFunctionCall @ exit #1 (bc#55, InadequateCoverage)` ×6
7. `FTL_PROOF PHASE2_DONE … retry_before=0 retry_after=1`

Pass-1 case9 only *allowed* FTL. This log shows FTL compiled **before** the phase change, then FTL ForceOSRExit → InadequateCoverage → per-site jettison.

First FTL-proof attempt used `if ($vm.ftlTrue()) saw.ftl = 1`, which planted a **second** ForceOSRExit and jettisoned during warmup. Fixed by `saw.ftl = $vm.ftlTrue()` on every call.

## Code size / compile cost

InadequateCoverage exit stubs (lazy, first hit):

- Baseline same-site stub sum (1 site): **512 B**
- Candidate same-site stub sum (1 site): **544 B** (**+32 B** load+cmp+branch on x86_64)
- Candidate 64 cold arms: 64 × 544 = **34816 B** vs expected 64 × 512 = 32768 B (**+2 KiB**, ~6%)

DFG compile time of the 64-arm function: ~1.0 ms candidate vs ~1.1 ms baseline warmup-only (noise). The extra codegen is on the **exit stub**, not the mainline. Objection is answerable: measurable, tiny.

## Official tests

`perl Tools/Scripts/run-jsc-stress-tests --jsc <jsc> JSTests/stress --filter inadequate-coverage`

| binary | same-site DFG | distinct-sites | same-site FTL |
| --- | --- | --- | --- |
| baseline | FAIL `retry=0` (right reason) | pass | FAIL `retry=0` (right reason) |
| candidate | pass (official runner + direct no-cjit) | pass | pass (direct + official) |

Do **not** pass `--osrExitCountForReoptimizationFromInadequateCoverage` in the tests: unpatched JSC with `--validateOptions=true` dies on the unknown option (exit 134), which would be a false baseline failure.

Concurrent JIT: the official tests are `runNoCJIT` / `runFTLNoCJIT` on purpose. Direct `useConcurrentJIT=true` failed `numberOfDFGCompiles < 1` before the phase change (async tier-up), not a policy failure.

`array-osr-exit-materialize-hole` (existing InadequateCoverage user) : no FAIL across its default/DFG/FTL variants.

## Style

`check-webkit-style` on the touched files reports hundreds of **pre-existing** indent/EOL issues in `OptionsList.h` / `DFGOperations.cpp`. No new issues were introduced on the added hunks that are not already the file's style. Cosmetic cleanup of those files was not done.

## Not tested

- ARM64, ARM32, RISC-V, macOS, Windows
- Full `JSTests/stress` / layout tests
- bun / FrozenMiniSearch product re-run on this HEAD
- WebKit EWS

## Verdict

**READY FOR UPSTREAM DRAFT**

Not READY FOR REVIEW: no Bugzilla id yet, one architecture, default changed from the pass-1 "5" after the per-site sweep.
