// Topology E: ES module. `let sink` here is module-lexical, not a JS global.
const INSERTS = 20000;
const UPDATES = 200000;
let sink = 0;

function scorePostingDoc(results, docId, termFreq) {
    const fieldLength = 1 + (docId & 7);
    const rawScore = termFreq * 2.2 / (termFreq + 1.2 * (0.3 + 0.7 * fieldLength));
    const weightedScore = 1.7 * rawScore;
    const result = results.get(docId);
    if (result) {
        result.score += weightedScore;
        sink ^= result.score | 0;
    } else
        results.set(docId, { score: weightedScore });
}

const results = new Map();
for (let i = 0; i < INSERTS; ++i)
    scorePostingDoc(results, i, 1 + (i & 3));
const start = (typeof preciseTime === "function") ? preciseTime() * 1000 : performance.now();
for (let i = 0; i < UPDATES; ++i)
    scorePostingDoc(results, i % INSERTS, 1 + (i & 3));
const elapsed = ((typeof preciseTime === "function") ? preciseTime() * 1000 : performance.now()) - start;
if (results.size !== INSERTS)
    throw new Error("unexpected result size: " + results.size);
const line = "REPRO name=topo-module-let-sink elapsed_ms=" + elapsed.toFixed(6) + " sink=" + sink + " size=" + results.size;
if (typeof print === "function")
    print(line);
else
    console.log(line);
