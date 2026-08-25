// Topology I: the hot loop lives inside an optimized function, not at top-level.
var out = (typeof print === "function") ? print : function (s) { console.log(s); };
var nowMs = (typeof preciseTime === "function") ? function () { return preciseTime() * 1000; } : function () { return performance.now(); };

var INSERTS = 20000;
var UPDATES = 200000;

function makeScorer() {
    var state = { sink: 0 };
    function scorePostingDoc(results, docId, termFreq) {
        var fieldLength = 1 + (docId & 7);
        var rawScore = termFreq * 2.2 / (termFreq + 1.2 * (0.3 + 0.7 * fieldLength));
        var weightedScore = 1.7 * rawScore;
        var result = results.get(docId);
        if (result) {
            result.score += weightedScore;
            state.sink ^= result.score | 0;
        } else
            results.set(docId, { score: weightedScore });
    }
    scorePostingDoc.state = state;
    return scorePostingDoc;
}

var scorePostingDoc = makeScorer();
function runPhase(results, n, mapId) {
    for (var i = 0; i < n; ++i)
        scorePostingDoc(results, mapId(i), 1 + (i & 3));
}

var results = new Map();
runPhase(results, INSERTS, function (i) { return i; });
var start = nowMs();
runPhase(results, UPDATES, function (i) { return i % INSERTS; });
if (results.size !== INSERTS)
    throw new Error("unexpected result size: " + results.size);
out("REPRO name=topo-inner-loop elapsed_ms=" + (nowMs() - start).toFixed(6) + " sink=" + scorePostingDoc.state.sink + " size=" + results.size);
