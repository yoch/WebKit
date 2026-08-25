// Performance reproducer derived from oven-sh/bun#40477:
// https://github.com/oven-sh/bun/issues/40477
// Original Bun reproducer:
// https://github.com/yoch/frozenminisearch/blob/61d4ee365fd31369bd07fa89cf9d26c596926dfb/benchmarks/jsc/inadequate-coverage-repro.js
//
// Intentional differences from the Bun version:
// - configuration is injected by the runner as REPRO_INSERTS/REPRO_UPDATES;
// - output uses print();
// - sink lives in closure state, not a shell global, to avoid the unrelated
//   jsc global UnprofiledWatchpoint jettison that masks InadequateCoverage.
// The scorePostingDoc hot-path shape is otherwise kept the same.

(function () {
    var INSERTS = typeof REPRO_INSERTS === "number" ? REPRO_INSERTS : 20000;
    var UPDATES = typeof REPRO_UPDATES === "number" ? REPRO_UPDATES : 200000;
    var state = { sink: 0 };

    function nowMs() {
        if (typeof preciseTime === "function")
            return preciseTime() * 1000;
        return +new Date();
    }

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

    noInline(scorePostingDoc);

    var results = new Map();

    // Phase 1: train/tier-up while the existing-result branch is never taken.
    for (var i = 0; i < INSERTS; ++i)
        scorePostingDoc(results, i, 1 + (i & 3));

    // Phase 2: immediately flip to the previously uncovered branch.
    var start = nowMs();
    for (var i = 0; i < UPDATES; ++i)
        scorePostingDoc(results, i % INSERTS, 1 + (i & 3));
    var elapsedMs = nowMs() - start;

    if (results.size !== INSERTS)
        throw new Error("unexpected result size: " + results.size);

    print("REPRO elapsed_ms=" + elapsedMs.toFixed(6)
        + " sink=" + state.sink
        + " size=" + results.size
        + " updates=" + UPDATES);
})();
