// Case 4: long phase A then long phase B. Rapid adaptation should help.
var out = (typeof print === "function") ? print : function (s) { console.log(s); };
var nowMs = (typeof preciseTime === "function") ? function () { return preciseTime() * 1000; } : function () { return performance.now(); };

var INSERTS = 20000;
var UPDATES = 200000;

function makeScorer() {
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
    score.state = state;
    return score;
}

var score = makeScorer();
if (typeof noInline === "function")
    noInline(score);
var results = new Map();
var t0 = nowMs();
for (var i = 0; i < INSERTS; ++i)
    score(results, i, 1 + (i & 3));
var phaseA = nowMs() - t0;
var t1 = nowMs();
for (var i = 0; i < UPDATES; ++i)
    score(results, i % INSERTS, 1 + (i & 3));
var phaseB = nowMs() - t1;
out("REPRO name=case4-phase-change phaseA_ms=" + phaseA.toFixed(6) + " phaseB_ms=" + phaseB.toFixed(6) + " sink=" + score.state.sink + " size=" + results.size + " dfg=" + ((typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(score) : -1));
