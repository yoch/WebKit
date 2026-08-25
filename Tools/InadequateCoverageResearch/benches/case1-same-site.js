// Case 1: same previously uncovered site becomes hot. Expect repeated InadequateCoverage at one site.
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
for (var i = 0; i < INSERTS; ++i)
    score(results, i, 1 + (i & 3));
var compilesBefore = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(score) : -1;
var start = nowMs();
for (var i = 0; i < UPDATES; ++i)
    score(results, i % INSERTS, 1 + (i & 3));
var elapsed = nowMs() - start;
var compilesAfter = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(score) : -1;
var retry = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(score) : -1;
out("REPRO name=case1-same-site elapsed_ms=" + elapsed.toFixed(6) + " sink=" + score.state.sink + " size=" + results.size + " dfg_before=" + compilesBefore + " dfg_after=" + compilesAfter + " retry=" + retry);
