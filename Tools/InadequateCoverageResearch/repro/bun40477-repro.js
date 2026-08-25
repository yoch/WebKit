// Standalone JSC adaptation of the Bun #40477 FrozenMiniSearch reproducer.
// Source: https://github.com/yoch/frozenminisearch/blob/61d4ee365fd31369bd07fa89cf9d26c596926dfb/benchmarks/jsc/inadequate-coverage-repro.js
// Downstream: https://github.com/oven-sh/bun/issues/40477
//
// Only intentional difference vs the original: `sink` lives in this IIFE
// instead of a shell global. A mutable global is a watchpoint in standalone
// JSC and historically jettisoned the CodeBlock after the first store
// (false negative). Map.get / existing-vs-new branch / result.score += /
// score formula / insert-then-update phases are unchanged.

var REPRO_INSERTS = (typeof REPRO_INSERTS === "number") ? REPRO_INSERTS : 20000;
var REPRO_UPDATES = (typeof REPRO_UPDATES === "number") ? REPRO_UPDATES : 200000;
var REPRO_MODE = (typeof REPRO_MODE === "string") ? REPRO_MODE : "phase2";
var REPRO_PROBE = !!REPRO_PROBE;

(function () {
    var out = (typeof print === "function") ? print : function (s) { console.log(s); };
    var nowMs = (typeof preciseTime === "function")
        ? function () { return preciseTime() * 1000; }
        : function () { return Date.now(); };

    var INSERTS = REPRO_INSERTS;
    var UPDATES = REPRO_UPDATES;
    var sink = 0;

    function scorePostingDoc(results, docId, termFreq) {
        var fieldLength = 1 + (docId & 7);
        var rawScore = termFreq * 2.2 / (termFreq + 1.2 * (0.3 + 0.7 * fieldLength));
        var weightedScore = 1.7 * rawScore;

        var result = results.get(docId);
        if (result) {
            result.score += weightedScore;
            sink ^= result.score | 0;
        } else {
            results.set(docId, { score: weightedScore });
        }
    }

    function fillInserts(results, n) {
        for (var i = 0; i < n; i++)
            scorePostingDoc(results, i, 1 + (i & 3));
    }

    // Wait for the concurrent compiler without changing tier-up
    // thresholds. Extra calls use fresh ids so the update arm stays
    // uncovered. This is not timed in phase2.
    function settleOptimized(results) {
        if (typeof numberOfDFGCompiles !== "function")
            return 0;
        var extra = 0;
        var nextId = results.size;
        var t = nowMs();
        while (numberOfDFGCompiles(scorePostingDoc) < 1 && extra < 200000 && nowMs() - t < 2000) {
            scorePostingDoc(results, nextId, 1);
            nextId++;
            extra++;
        }
        return extra;
    }

    function runUpdates(results, n) {
        for (var i = 0; i < n; i++)
            scorePostingDoc(results, i % INSERTS, 1 + (i & 3));
    }

    function probe(label) {
        if (!REPRO_PROBE)
            return;
        var dfg = (typeof numberOfDFGCompiles === "function") ? numberOfDFGCompiles(scorePostingDoc) : -1;
        var retry = (typeof reoptimizationRetryCount === "function") ? reoptimizationRetryCount(scorePostingDoc) : -1;
        out("PROBE " + label + " dfg=" + dfg + " retry=" + retry);
    }

    var results = new Map();
    var t0;
    var elapsed;
    var extra = "";
    var settled = 0;

    if (REPRO_MODE === "insert-only") {
        t0 = nowMs();
        fillInserts(results, INSERTS);
        elapsed = nowMs() - t0;
        probe("after_inserts");
    } else if (REPRO_MODE === "update-only") {
        fillInserts(results, INSERTS);
        settled = settleOptimized(results);
        runUpdates(results, Math.min(4000, Math.max(INSERTS, 4000)));
        probe("after_profile");
        t0 = nowMs();
        runUpdates(results, UPDATES);
        elapsed = nowMs() - t0;
        probe("after_steady");
    } else if (REPRO_MODE === "mixed") {
        t0 = nowMs();
        for (var i = 0; i < INSERTS; i++) {
            scorePostingDoc(results, i, 1 + (i & 3));
            if (i > 0)
                scorePostingDoc(results, i - 1, 1 + (i & 3));
        }
        elapsed = nowMs() - t0;
        probe("after_mixed");
    } else if (REPRO_MODE === "windows") {
        fillInserts(results, INSERTS);
        settled = settleOptimized(results);
        probe("after_inserts");
        var edges = [8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096];
        var prev = 0;
        var parts = [];
        for (var w = 0; w < edges.length; w++) {
            var n = edges[w] - prev;
            t0 = nowMs();
            for (var i = 0; i < n; i++)
                scorePostingDoc(results, (prev + i) % INSERTS, 1 + ((prev + i) & 3));
            parts.push((prev + 1) + "-" + edges[w] + "=" + (nowMs() - t0).toFixed(3));
            prev = edges[w];
        }
        elapsed = 0;
        extra = " " + parts.join(" ");
        probe("after_windows");
    } else {
        fillInserts(results, INSERTS);
        settled = settleOptimized(results);
        probe("after_inserts");
        t0 = nowMs();
        runUpdates(results, UPDATES);
        elapsed = nowMs() - t0;
        probe("after_phase2");
    }

    if (REPRO_MODE !== "mixed" && results.size < INSERTS)
        throw new Error("unexpected result size: " + results.size);

    out("REPRO elapsed_ms=" + elapsed.toFixed(6) + " sink=" + sink + " size=" + results.size
        + " inserts=" + INSERTS + " updates=" + UPDATES + " mode=" + REPRO_MODE
        + " settled=" + settled + extra);
})();
