//@ if isFTLEnabled then runFTLNoCJIT("--osrExitCountForReoptimization=1000", "--osrExitCountForReoptimizationFromLoop=1000", "--thresholdForFTLOptimizeAfterWarmUp=1000", "--thresholdForFTLOptimizeSoon=1000") else skip end

// Same-site InadequateCoverage must reoptimize even when the ForceOSRExit
// is in FTL code. `$vm.ftlTrue()` is constant-folded only in FTL.
// Assign the flag on every call so the store is not itself a SpecNone
// ForceOSRExit. FromLoop is raised to 1000 so a loop-stuck budget cannot
// make this pass without the per-site policy.

(function () {
    var saw = { ftl: false };
    var object = { x: 1 };

    function f(mode, object) {
        saw.ftl = $vm.ftlTrue();
        if (mode)
            return object.x;
        return 0;
    }

    noInline(f);

    for (var i = 0; i < testLoopCount; ++i) {
        f(0, object);
        if (i === 200 || i === 1200)
            optimizeNextInvocation(f);
    }

    if (!saw.ftl)
        throw new Error("expected FTL compile of f before the phase change");
    if (reoptimizationRetryCount(f) !== 0)
        throw new Error("warmup must not jettison, retry=" + reoptimizationRetryCount(f));

    var retryBefore = reoptimizationRetryCount(f);
    var sum = 0;
    for (var i = 0; i < 40; ++i)
        sum += f(1, object);

    if (sum !== 40)
        throw new Error("mode=1 arm never ran, sum=" + sum);
    if (reoptimizationRetryCount(f) <= retryBefore)
        throw new Error("FTL same-site InadequateCoverage should have jettisoned within 40 repeats, retry=" + reoptimizationRetryCount(f) + " before=" + retryBefore);
})();
