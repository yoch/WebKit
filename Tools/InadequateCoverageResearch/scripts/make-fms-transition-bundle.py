#!/usr/bin/env python3
"""Add outer-harness transition timing to the generated issue4 bundle.

The product/search functions are untouched. Only measureSearch and the emitted
report gain successive per-search timings before the existing warmup/calibrate
and settled measurement.
"""

from __future__ import annotations

import argparse
from pathlib import Path

OLD_MEASURE = """  function measureSearch(run) {
      for (let i = 0; i < 8; i++)
          consume(run());
      const batch = calibrate(run);
      const values = new Array(SEARCH_SAMPLES);
      for (let i = 0; i < SEARCH_SAMPLES; i++)
          values[i] = runBatch(run, batch) * 1000 / batch;
      return {
          medianUs: median(values),
          minUs: Math.min(...values),
          maxUs: Math.max(...values),
          batch,
          samples: SEARCH_SAMPLES,
      };
  }
"""

NEW_MEASURE = """  let transitionEvidence = null;
  function measureSearch(run) {
      const firstSearchesUs = new Array(32);
      for (let i = 0; i < firstSearchesUs.length; i++) {
          const started = nowMs();
          consume(run());
          firstSearchesUs[i] = (nowMs() - started) * 1000;
      }
      for (let i = 0; i < 8; i++)
          consume(run());
      const batch = calibrate(run);
      const values = new Array(SEARCH_SAMPLES);
      for (let i = 0; i < SEARCH_SAMPLES; i++)
          values[i] = runBatch(run, batch) * 1000 / batch;
      transitionEvidence = { firstSearchesUs };
      return {
          medianUs: median(values),
          minUs: Math.min(...values),
          maxUs: Math.max(...values),
          batch,
          samples: SEARCH_SAMPLES,
      };
  }
"""

OLD_REPORT = """        timings,
        sink: blackhole >>> 0,
"""

NEW_REPORT = """        timings,
        transition: transitionEvidence,
        sink: blackhole >>> 0,
"""


def replace_once(source: str, old: str, new: str, name: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"expected one {name}, found {count}")
    return source.replace(old, new, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()
    source = Path(args.input).read_text()
    source = replace_once(source, OLD_MEASURE, NEW_MEASURE, "measureSearch")
    source = replace_once(source, OLD_REPORT, NEW_REPORT, "report insertion")
    Path(args.output).write_text(source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
