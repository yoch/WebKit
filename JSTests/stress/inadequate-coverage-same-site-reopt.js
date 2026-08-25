//@ skip if not $jitTests
//@ runNoCJIT("--useFTLJIT=false", "--osrExitCountForReoptimization=1000")

// Warm up only the mode=0 arm so `object.x` is compiled as ForceOSRExit
// (SpecNone). Switching to mode=1 must reoptimize from repeated same-site
// InadequateCoverage without waiting for the generic 1000-exit budget.
//
// Object state is passed as an argument so a shell global watchpoint cannot
// jettison the CodeBlock after the first exit.

function f(mode, object) {
    if (mode)
        return object.x;
    return 0;
}

noInline(f);
noFTL(f);

(function () {
    var object = { x: 1 };
    for (var i = 0; i < testLoopCount; ++i)
        f(0, object);

    if (numberOfDFGCompiles(f) < 1)
        throw new Error("expected DFG compile after mode=0 warmup");

    var retryBefore = reoptimizationRetryCount(f);
    var sum = 0;
    for (var i = 0; i < 40; ++i)
        sum += f(1, object);

    if (sum !== 40)
        throw new Error("mode=1 arm never ran, sum=" + sum);
    if (reoptimizationRetryCount(f) <= retryBefore)
        throw new Error("same-site InadequateCoverage should have jettisoned within 40 repeats, retry=" + reoptimizationRetryCount(f) + " before=" + retryBefore);
})();
