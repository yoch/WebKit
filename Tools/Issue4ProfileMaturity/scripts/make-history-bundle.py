#!/usr/bin/env python3
"""Build a resident-pressure variant with a chosen search history.

The product search functions are untouched. Only the outer `workloads`
object and optional extra multi warmup change.
"""

from __future__ import annotations

import argparse
from pathlib import Path

WORKLOADS = {
    "brand": "          'resident-brand': () => runSearch(corpora, targets, 'doliprane'),",
    "substance": "          'resident-substance': () => runSearch(corpora, targets, 'paracetamol'),",
    "multi": "          'resident-multi': () => runSearch(corpora, targets, 'amoxicilline 500'),",
    "fuzzy": "          'resident-fuzzy': () => runSearch(corpora, targets, 'paracetmol'),",
}

OLD = """      const workloads = {
          'resident-brand': () => runSearch(corpora, targets, 'doliprane'),
          'resident-substance': () => runSearch(corpora, targets, 'paracetamol'),
          'resident-multi': () => runSearch(corpora, targets, 'amoxicilline 500'),
          'resident-fuzzy': () => runSearch(corpora, targets, 'paracetmol'),
      };"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument(
        "--history",
        required=True,
        help="comma-separated prefix+multi, e.g. brand,multi or brand,substance,fuzzy,multi",
    )
    parser.add_argument(
        "--extra-multi-searches",
        type=int,
        default=0,
        help="consume() extra multi searches before the measured multi workload",
    )
    args = parser.parse_args()
    names = [part.strip() for part in args.history.split(",") if part.strip()]
    if "multi" not in names:
        raise SystemExit("history must include multi")
    unknown = [name for name in names if name not in WORKLOADS]
    if unknown:
        raise SystemExit(f"unknown workload names: {unknown}")
    body = "      const workloads = {\n" + "\n".join(WORKLOADS[name] for name in names) + "\n      };"
    extra = ""
    if args.extra_multi_searches:
        extra = f"""      for (let i = 0; i < {args.extra_multi_searches}; i++)
          consume(runSearch(corpora, targets, 'amoxicilline 500'));
"""
    source = Path(args.input).read_text()
    if source.count(OLD) != 1:
        raise SystemExit(f"expected one workloads block, found {source.count(OLD)}")
    Path(args.output).write_text(source.replace(OLD, extra + body, 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
