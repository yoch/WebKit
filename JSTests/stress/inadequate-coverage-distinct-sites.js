//@ skip if not $jitTests
//@ requireOptions("--useConcurrentJIT=0", "--useFTLJIT=0", "--osrExitCountForReoptimization=1000")

// Eight distinct uncovered sites, each hit once, must not share a per-site
// InadequateCoverage budget. Global threshold is 1000, so this must not reopt.

function coldSites(mode, a, b, c, d, e, f, g, h) {
    if (mode === 1)
        return a.x;
    if (mode === 2)
        return b.x;
    if (mode === 3)
        return c.x;
    if (mode === 4)
        return d.x;
    if (mode === 5)
        return e.x;
    if (mode === 6)
        return f.x;
    if (mode === 7)
        return g.x;
    if (mode === 8)
        return h.x;
    return 0;
}

noInline(coldSites);
noFTL(coldSites);

var a = { x: 1 };
var b = { x: 2 };
var c = { x: 3 };
var d = { x: 4 };
var e = { x: 5 };
var f = { x: 6 };
var g = { x: 7 };
var h = { x: 8 };

for (var i = 0; i < testLoopCount; ++i)
    coldSites(0, a, b, c, d, e, f, g, h);

if (numberOfDFGCompiles(coldSites) < 1)
    throw new Error("expected DFG compile after default-arm warmup");

var compilesBefore = numberOfDFGCompiles(coldSites);
var retryBefore = reoptimizationRetryCount(coldSites);

var sum = 0;
for (var mode = 1; mode <= 8; ++mode)
    sum += coldSites(mode, a, b, c, d, e, f, g, h);

if (sum !== 36)
    throw new Error("bad sum: " + sum);
if (numberOfDFGCompiles(coldSites) !== compilesBefore)
    throw new Error("distinct InadequateCoverage sites must not share the aggressive budget, compiles=" + numberOfDFGCompiles(coldSites));
if (reoptimizationRetryCount(coldSites) !== retryBefore)
    throw new Error("distinct sites should not increment the reoptimization retry counter");
