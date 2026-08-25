// Topology D/jsc-script: top-level `var sink` is a JS global on standalone jsc.
var out = (typeof print === "function") ? print : function (s) { console.log(s); };
var nowMs = (typeof preciseTime === "function") ? function () { return preciseTime() * 1000; } : function () { return performance.now(); };

var INSERTS = 20000;
var UPDATES = 200000;
var sink = 0;

function scorePostingDoc(results, docId, termFreq) {
    var fieldLength = 1 + (docId & 7);
    var rawScore = termFreq * 2.2 / (termFreq + 1.2 * (0.3 + 0.7 * fieldLength));
    var weightedScore = 1.7 * rawScore;
    var result = results.get(docId);
    if (result) {
        result.score += weightedScore;
        sink ^= result.score | 0;
    } else
        results.set(docId, { score: weightedScore });
}

var results = new Map();
for (var i = 0; i < INSERTS; ++i)
    scorePostingDoc(results, i, 1 + (i & 3));
var start = nowMs();
for (var i = 0; i < UPDATES; ++i)
    scorePostingDoc(results, i % INSERTS, 1 + (i & 3));
if (results.size !== INSERTS)
    throw new Error("unexpected result size: " + results.size);
out("REPRO name=topo-global-var-sink elapsed_ms=" + (nowMs() - start).toFixed(6) + " sink=" + sink + " size=" + results.size);
