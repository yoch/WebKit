# InadequateCoverage research notes

## Exact SHAs recorded at investigation start

| Tree | SHA | Date (commit) |
| --- | --- | --- |
| `yoch/WebKit` `origin/main` / workspace HEAD | `5549b3663c5d3904eab780389cd14c58523d1dfa` | 2026-08-25 |
| Upstream `WebKit/WebKit` `main` (API) | `34a2ffae86c5154b16af0975c901c21ae744d8e4` | 2026-08-25T18:54:20Z |
| Bun canary under test | `1.4.1-canary.1+11fb73032` / `11fb73032c91b4099691279b02852a9c9491e036` | |
| Bun-pinned `oven-sh/WebKit` | `cb61607f1a4bae79d7701965062634dee9efb349` | |
| Historical standalone `jsc` binary | bun-webkit autobuild `cb61607f1a4bae79d7701965062634dee9efb349` | |

Existing research branches (inspected, not rewritten):

| Branch | Tip | Contents |
| --- | --- | --- |
| `origin/research/jsc-inadequate-coverage` | `724699812de75977c8307c3492ce47d5d7805e5e` | GHA workflow only (clang 18 + libstdc++, known-bad harness) |
| `origin/research/jsc-inadequate-coverage-per-site` | `c50afdff29aa…` | per-site candidate patch + workflow |
| `origin/cursor/setup-webkit-jsc-env-7a5a` | `bfb35d6e55e7…` | clang-20 + libc++ install notes |

## Code path (verified in `5549b366`)

1. `ByteCodeParser::getPrediction()` (`DFGByteCodeParser.cpp`): `SpecNone` → `addToGraph(ForceOSRExit)` with comment “Give up on executing this code, since we're likely to do more damage than good.”
2. `pruneUnreachableNodes()` plants `Unreachable` after `ForceOSRExit`.
3. DFG: `ForceOSRExit` → `terminateSpeculativeExecution(InadequateCoverage, …)`.
4. FTL: `compileForceOSRExit()` → `terminate(InadequateCoverage)`.
5. `handleExitCounts()` increments `OSRExit::m_count` and `CodeBlock::osrExitCounter`.
6. Threshold compare uses `BelowOrEqual` against a **compile-time constant** (`exitCountThresholdForReoptimization()`), so effective trigger is `count > threshold` (threshold 100 → 101 exits).
7. FromLoop threshold (5) is selected only when an **inlined** frame’s executable has `DidTryToEnterInLoop`. Outermost call-entry exits use 100 even if the function itself OSR-entered from a loop.
8. `operationTriggerReoptimizationNow()` jettisons when `shouldReoptimizeNow()` (`>= 100`) or stuck-in-loop (`>= 5` plus loop heuristics).
9. `adjustedExitCountThreshold()` doubles the budget per `reoptimizationRetryCounter`.

`InadequateCoverage` has **no** dedicated policy. `exitKindMayJettison` excludes only `ExceptionCheck` / `GenericUnwind`.

## Off-by-one (do not choose intuitively)

| Path | Compare | Threshold 100 | Threshold 5 |
| --- | --- | --- | --- |
| JIT `handleExitCounts` | `BelowOrEqual` → skip; reopt when `>` | 101st exit | 6th exit |
| C++ `shouldReoptimizeNow` | `>=` | would fire at 100, but JIT never calls it at 100 | same mismatch |

Observed Bun/jsc counts (101 / 2 / 1001) match the JIT `>` convention, not the C++ `>=`.

## Archaeology

- `osrExitCountForReoptimization = 100` and `…FromLoop = 5` date to bug 90146 (2012): “DFG recompilation heuristics should be based on count, not rate” (`455479773fe8` / reland `49e85deef018`). They are generic speculation-failure hysteresis, not InadequateCoverage-specific.
- Bug 90420 is the Options machinery, not this policy.
- `ForceOSRExit` / `InadequateCoverage` arrive with the FTL/fourthTier work (2013). Keeping a ForceOSRExit on never-executed bytecode is intentional.
- Profile-coverage delay already exists at **tier-up** (`desiredProfileLivenessRate=0.75`, `desiredProfileFullnessRate=0.35`) and can plateau on large functions. That is why a late-taken branch can still be `SpecNone` after DFG compile.

## Existing research patches (inspected)

1. FrozenMiniSearch PR 14: reuse **global** FromLoop (5) whenever the exit *kind* is InadequateCoverage. Minimal, but aggregates distinct sites.
2. `research/jsc-inadequate-coverage-per-site`: new option + `OSRExit::m_count > threshold`. Semantically stronger; uses `Above` (same `>` convention). Adds a VM option.

Neither is treated as validated until this harness reproduces and the adversarial cases run.
