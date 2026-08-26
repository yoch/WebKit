# JSC source notes (upstream `cab391584f80`)

Facts, not inferences. All citations are this tree.

## ForceOSRExit / InadequateCoverage

`DFGByteCodeParser::getPrediction()` inserts `ForceOSRExit` when the
value profile for the current bytecode is `SpecNone`:

```1322:1332:Source/JavaScriptCore/dfg/DFGByteCodeParser.cpp
    SpeculatedType getPrediction(BytecodeIndex bytecodeIndex)
    {
        SpeculatedType prediction = getPredictionWithoutOSRExit(bytecodeIndex);

        if (prediction == SpecNone) {
            // We have no information about what values this node generates. Give up
            // on executing this code, since we're likely to do more damage than good.
            addToGraph(ForceOSRExit);
        }
```

DFG lowering (`DFGSpeculativeJIT64.cpp`) and FTL lowering
(`FTLLowerDFGToB3.cpp`) map `ForceOSRExit` to OSR exit kind
`InadequateCoverage`. The comment on the node type calls it a
pseudo-terminal. This is intentional and sound.

Other `ForceOSRExit` insertions exist (structure-filter empty set,
unresolved property, etc.). They are not all SpecNone value profiles.

## Reoptimization is an aggregate exit-count policy

`handleExitCounts` (`DFGOSRExitCompilerCommon.cpp`) increments both
per-exit `m_count` and CodeBlock `osrExitCounter`. The threshold is
`osrExitCountForReoptimization` (**100**) unless an inlined frame has
`DidTryToEnterInLoop`, in which case it uses
`osrExitCountForReoptimizationFromLoop` (**5**).

Call-entry phase changes therefore use 100, not 5. That matches the
standalone 101/2/1001 InadequateCoverage counts on the old micro-repro.

`operationTriggerReoptimizationNow` double-checks `shouldReoptimizeNow()`
/ `shouldReoptimizeFromLoopNow()` and otherwise calls
`optimizeAfterLongWarmUp()`. Jettison increments
`reoptimizationRetryCounter`, which exponentially scales the next
optimization threshold (`1 << retry`).

**There is no InadequateCoverage-specific threshold on this upstream
tree.** The parked fork candidate added one; it is not present here.

## Profile-maturity gating already exists — but only for first DFG

`CodeBlock::shouldOptimizeNowFromBaseline()` (`CodeBlock.cpp` ~3119):

- require `desiredProfileLivenessRate` (0.75) and
  `desiredProfileFullnessRate` (0.35);
- `minimumOptimizationDelay` 1 / `maximumOptimizationDelay` 5;
- for large CodeBlocks, plateau detection if liveness/fullness did not
  change since the last sample.

This gate is **not** re-applied as a condition on "the SpecNone bytecode
that just caused InadequateCoverage is now live". After jettison, the
next DFG compile uses the same first-compile gate on the whole
CodeBlock, plus a higher execution threshold from the retry counter.

## Implication for the coverage-aware hypothesis

A site-specific "wait until this profile is non-SpecNone, then
recompile" policy does **not** already exist. The closest reusable
abstraction is `shouldOptimizeNowFromBaseline`'s liveness/fullness math.

CURRENT already waits ~100 baseline trips on a deterministic
ForceOSRExit before jettison — that *is* a crude coverage wait. Cutting
it to 5 (OLD-EARLY / parked patch) is "recompile before the new path
has many samples".

`maximumOptimizationDelay=5` **overrides** the liveness/fullness gate:
after five delays, `shouldOptimizeNowFromBaseline` returns true even if
liveness is still 0.38. FULL `scorePostingDoc` did exactly that before
its first DFG (3840B). That is the opposite of “wait until the required
profile is live.”

The OSR exit record already carries the bytecode index (`bc#430` on
`scorePostingDoc` InadequateCoverage in the BM dump). Associating the
SpecNone origin with the exit is therefore cheap; JSC just does not
use that index as a maturity wait.

`reoptimizationRetryCounterMax` starts at 0 in `OptionsList.h` and is
raised at startup in `Options.cpp` until
`thresholdForOptimizeAfterLongWarmUp << (max+1)` would overflow int32.
Jettison therefore exponentially raises the next optimization threshold
(`CodeBlock.cpp` ~2581). That is a plausible reason FULL emits many
DFG `scorePostingDoc` recompiles and never the isolated-multi FTL 5184
inside the measured process.
