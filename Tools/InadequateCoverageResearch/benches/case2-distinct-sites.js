// Case 2: eight distinct uncovered property loads, each hit once.
// A correct per-site policy must not treat this as eight repeats of one site.
var out = (typeof print === "function") ? print : function (s) { console.log(s); };

function coldSites(mode, a, b, c, d, e, f, g, h) {
    if (mode === 1) return a.x;
    if (mode === 2) return b.x;
    if (mode === 3) return c.x;
    if (mode === 4) return d.x;
    if (mode === 5) return e.x;
    if (mode === 6) return f.x;
    if (mode === 7) return g.x;
    if (mode === 8) return h.x;
    return 0;
}
if (typeof noInline === "function")
    noInline(coldSites);
if (typeof noFTL === "function")
    noFTL(coldSites);

var a = { x: 1 }, b = { x: 2 }, c = { x: 3 }, d = { x: 4 };
var e = { x: 5 }, f = { x: 6 }, g = { x: 7 }, h = { x: 8 };
for (var i = 0; i < 20000; ++i)
    coldSites(0, a, b, c, d, e, f, g, h);
var before = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(coldSites) : -1;
var sum = 0;
for (var mode = 1; mode <= 8; ++mode)
    sum += coldSites(mode, a, b, c, d, e, f, g, h);
var after = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(coldSites) : -1;
var retry = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(coldSites) : -1;
out("REPRO name=case2-distinct-sites sum=" + sum + " dfg_before=" + before + " dfg_after=" + after + " retry=" + retry);
