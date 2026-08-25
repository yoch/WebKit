# InadequateCoverage research harness

Independent reproduction and adversarial microbenchmarks for JavaScriptCore
`ForceOSRExit` / `InadequateCoverage` reoptimization.

This directory is **not** an upstream WebKit change. Policy patches live on
sibling branches.

## Layout

- `benches/` — topology variants (global / module / closure / wrapper / loop)
  and cases 1–9 from the investigation brief
- `scripts/run-matrix.py` — drives `jsc` or `bun` across thresholds
- `MATRIX.md` — measured results
- `NOTES.md` — code-path and archaeology notes

## Run

```bash
python3 Tools/InadequateCoverageResearch/scripts/run-matrix.py \
  --jsc /path/to/jsc --engine jsc --tag my-run \
  --thresholds 100,5,1
```

Bun (exact canary used here: `1.4.1-canary.1+11fb73032`):

```bash
python3 Tools/InadequateCoverageResearch/scripts/run-matrix.py \
  --bun ~/.bun/bin/bun --engine bun --tag bun-run \
  --thresholds 100,5,1
```
