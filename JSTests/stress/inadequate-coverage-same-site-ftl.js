//@ if isFTLEnabled then runFTLNoCJIT("--osrExitCountForReoptimization=1000", "--thresholdForFTLOptimizeAfterWarmUp=1000", "--thresholdForFTLOptimizeSoon=1000") else skip end

// Same-site InadequateCoverage must reoptimize even when the ForceOSRExit
// is in FTL code. `$vm.ftlTrue()` is constant-folded only in FTL, so the
// mode=0 warmup is required to reach FTL before the phase change.
//
// The FTL flag is a replace-store to a pre-existing property on a closure
// object so a structure transition cannot jettison the CodeBlock.

(function () {
    var saw = { ftl: 0 };
    var object = { x: 1 };

    function f(mode, object) {
        if ($vm.ftlTrue())
            saw.ftl = 1;
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

    var retryBefore = reoptimizationRetryCount(f);
    var sum = 0;
    for (var i = 0; i < 40; ++i)
        sum += f(1, object);

    if (sum !== 40)
        throw new Error("mode=1 arm never ran, sum=" + sum);
    if (reoptimizationRetryCount(f) <= retryBefore)
        throw new Error("FTL same-site InadequateCoverage should have jettisoned within 40 repeats, retry=" + reoptimizationRetryCount(f) + " before=" + retryBefore);
})();
