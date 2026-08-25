# InadequateCoverage research harness (v2)

Per-site threshold sweep and FTL / compile-cost probes for the
InadequateCoverage reoptimization candidate.

```
python3 Tools/InadequateCoverageResearch/scripts/run-persite-sweep.py \
  --jsc /tmp/ic-research-v2/candidate/bin/jsc \
  --tag v2-candidate --include-ftl --include-cost --include-coupling

python3 Tools/InadequateCoverageResearch/scripts/run-persite-sweep.py \
  --jsc /tmp/ic-research-v2/baseline/bin/jsc \
  --tag v2-baseline --baseline --include-ftl --include-cost
```
