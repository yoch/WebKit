//@ skip if not $jitTests
//@ requireOptions("--useConcurrentJIT=0", "--useFTLJIT=0", "--osrExitCountForReoptimization=1000")

// Same previously uncovered DFG site becoming hot must reoptimize without
// waiting for the generic 1000-exit budget. The per-site InadequateCoverage
// policy uses osrExitCountForReoptimizationFromLoop (default 5) with the
// existing JIT `count > threshold` convention, so ~6 repeats are enough.

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
noInline(score);
noFTL(score);

var results = new Map();
for (var i = 0; i < testLoopCount; ++i)
    score(results, i);

if (numberOfDFGCompiles(score) < 1)
    throw new Error("expected DFG compile after insert-only warmup");

var compilesBeforePhaseChange = numberOfDFGCompiles(score);
var retryBefore = reoptimizationRetryCount(score);

for (var i = 0; i < 40; ++i)
    score(results, i);

if (results.size !== testLoopCount)
    throw new Error("unexpected result size: " + results.size);
if (results.get(0).score !== 2)
    throw new Error("update branch never ran, score=" + results.get(0).score);
// 40 repeats is enough to cross the per-site FromLoop bar (count > 5) but
// below the generic 1000-exit budget. Jettison increments the retry
// counter even if we have not yet run long enough to compile again.
if (reoptimizationRetryCount(score) <= retryBefore)
    throw new Error("same-site InadequateCoverage should have jettisoned within 40 repeats, retry=" + reoptimizationRetryCount(score) + " before=" + retryBefore + " compiles=" + numberOfDFGCompiles(score) + "/" + compilesBeforePhaseChange);
