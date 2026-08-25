#!/usr/bin/env python3
"""Collect raw FMS experiment JSON files into one committed evidence artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

GITHUB_SAMPLE = re.compile(
    r"(?P<repetition>\d{2})\.(?P<position>\d) "
    r"(?P<condition>default|global-1)\s+"
    r"(?P<median>[0-9.]+) us fp=(?P<fingerprint>[0-9a-f]+)"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="label=/path/to/result.json",
    )
    parser.add_argument(
        "--github-log",
        action="append",
        default=[],
        help="label=/path/to/gh-run-log; extracts printed raw samples",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    evidence = {}
    for item in args.input:
        label, raw_path = item.split("=", 1)
        evidence[label] = json.loads(Path(raw_path).read_text())
    for item in args.github_log:
        label, raw_path = item.split("=", 1)
        rows = []
        for match in GITHUB_SAMPLE.finditer(Path(raw_path).read_text()):
            rows.append(
                {
                    "repetition": int(match.group("repetition")),
                    "position": int(match.group("position")),
                    "condition": match.group("condition"),
                    "median_us": float(match.group("median")),
                    "fingerprint": match.group("fingerprint"),
                }
            )
        evidence[label] = {"raw": rows, "sample_count": len(rows)}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"wrote {output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
