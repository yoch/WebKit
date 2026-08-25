// Case 3: the uncovered branch is taken once. Must not compile-storm.
var out = (typeof print === "function") ? print : function (s) { console.log(s); };

function makeScorer() {
    var state = { sink: 0 };
    function score(results, docId) {
        var result = results.get(docId);
        if (result) {
            result.score += 1;
            state.sink ^= result.score;
        } else
            results.set(docId, { score: 1 });
    }
    score.state = state;
    return score;
}

var score = makeScorer();
if (typeof noInline === "function")
    noInline(score);
if (typeof noFTL === "function")
    noFTL(score);
var results = new Map();
for (var i = 0; i < 20000; ++i)
    score(results, i);
var before = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(score) : -1;
score(results, 0);
var after = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(score) : -1;
var retry = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(score) : -1;
out("REPRO name=case3-rare-branch sink=" + score.state.sink + " dfg_before=" + before + " dfg_after=" + after + " retry=" + retry);
