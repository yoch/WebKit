// Case 8: same phase-change, but the scorer is small and should be inlined into the driver.
var out = (typeof print === "function") ? print : function (s) { console.log(s); };
var nowMs = (typeof preciseTime === "function") ? function () { return preciseTime() * 1000; } : function () { return performance.now(); };

var INSERTS = 20000;
var UPDATES = 200000;
var state = { sink: 0 };

function score(results, docId, termFreq) {
    var weightedScore = 1.7 * termFreq;
    var result = results.get(docId);
    if (result) {
        result.score += weightedScore;
        state.sink ^= result.score | 0;
    } else
        results.set(docId, { score: weightedScore });
}

function driver(results, n, mapId) {
    for (var i = 0; i < n; ++i)
        score(results, mapId(i), 1 + (i & 3));
}

if (typeof noInline === "function")
    noInline(driver);

var results = new Map();
driver(results, INSERTS, function (i) { return i; });
var start = nowMs();
driver(results, UPDATES, function (i) { return i % INSERTS; });
out("REPRO name=case8-inlined elapsed_ms=" + (nowMs() - start).toFixed(6) + " sink=" + state.sink + " size=" + results.size + " dfg_driver=" + ((typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(driver) : -1));
