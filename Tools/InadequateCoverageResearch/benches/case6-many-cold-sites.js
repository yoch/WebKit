// Case 6: many distinct cold arms, each touched a few times.
// Adversarial against a global InadequateCoverage budget.
var out = (typeof print === "function") ? print : function (s) { console.log(s); };
var nowMs = (typeof preciseTime === "function") ? function () { return preciseTime() * 1000; } : function () { return performance.now(); };

function many(mode, o) {
    switch (mode) {
    case 0: return o.a0;
    case 1: return o.a1;
    case 2: return o.a2;
    case 3: return o.a3;
    case 4: return o.a4;
    case 5: return o.a5;
    case 6: return o.a6;
    case 7: return o.a7;
    case 8: return o.a8;
    case 9: return o.a9;
    case 10: return o.a10;
    case 11: return o.a11;
    case 12: return o.a12;
    case 13: return o.a13;
    case 14: return o.a14;
    case 15: return o.a15;
    case 16: return o.a16;
    case 17: return o.a17;
    case 18: return o.a18;
    case 19: return o.a19;
    case 20: return o.a20;
    case 21: return o.a21;
    case 22: return o.a22;
    case 23: return o.a23;
    case 24: return o.a24;
    case 25: return o.a25;
    case 26: return o.a26;
    case 27: return o.a27;
    case 28: return o.a28;
    case 29: return o.a29;
    case 30: return o.a30;
    case 31: return o.a31;
    default: return 0;
    }
}
if (typeof noInline === "function")
    noInline(many);
if (typeof noFTL === "function")
    noFTL(many);

var o = {};
for (var i = 0; i < 32; ++i)
    o["a" + i] = i + 1;

for (var i = 0; i < 20000; ++i)
    many(0, o);
var before = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(many) : -1;
var start = nowMs();
var sum = 0;
// Each non-zero arm is touched three times — below a per-site 5, above a global 5 once enough arms fire.
for (var pass = 0; pass < 3; ++pass) {
    for (var mode = 1; mode < 32; ++mode)
        sum += many(mode, o);
}
var elapsed = nowMs() - start;
var after = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(many) : -1;
var retry = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(many) : -1;
out("REPRO name=case6-many-cold-sites elapsed_ms=" + elapsed.toFixed(6) + " sum=" + sum + " dfg_before=" + before + " dfg_after=" + after + " retry=" + retry);
