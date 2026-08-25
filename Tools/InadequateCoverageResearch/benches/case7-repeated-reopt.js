// Case 7: sequential durable phase changes. After each reopt the retry counter
// should exponentially raise the next InadequateCoverage budget.
var out = (typeof print === "function") ? print : function (s) { console.log(s); };
var nowMs = (typeof preciseTime === "function") ? function () { return preciseTime() * 1000; } : function () { return performance.now(); };

function multi(mode, o) {
    if (mode === 0) return o.a;
    if (mode === 1) return o.b;
    if (mode === 2) return o.c;
    if (mode === 3) return o.d;
    return o.e;
}
if (typeof noInline === "function")
    noInline(multi);
if (typeof noFTL === "function")
    noFTL(multi);

var o = { a: 1, b: 2, c: 3, d: 4, e: 5 };
var start = nowMs();
for (var i = 0; i < 30000; ++i)
    multi(0, o);
var after0 = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(multi) : -1;
for (var i = 0; i < 30000; ++i)
    multi(1, o);
var after1 = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(multi) : -1;
for (var i = 0; i < 30000; ++i)
    multi(2, o);
var after2 = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(multi) : -1;
for (var i = 0; i < 30000; ++i)
    multi(3, o);
var after3 = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(multi) : -1;
var retry = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(multi) : -1;
out("REPRO name=case7-repeated-reopt elapsed_ms=" + (nowMs() - start).toFixed(6) + " dfg0=" + after0 + " dfg1=" + after1 + " dfg2=" + after2 + " dfg3=" + after3 + " retry=" + retry);
