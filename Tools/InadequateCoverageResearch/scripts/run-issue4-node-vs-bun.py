#!/usr/bin/env python3
"""Interleaved Node-vs-Bun comparison of the issue #4 resident-multi flip.

Runs every (runtime, bundle) pair as independent processes in shuffled order
and reports the multi-term timing plus the simple-search timings when the
bundle provides them.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import subprocess
from pathlib import Path

PREFIX = "@@FROZEN_ENGINE_BENCH@@"
MULTI_KEYS = ("i4-multi-only", "resident-multi")


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * p / 100
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - position) + ordered[high] * (position - low)


def mann_whitney(a: list[float], b: list[float]) -> dict[str, float]:
    combined = sorted([(value, 0) for value in a] + [(value, 1) for value in b])
    ranks = [0.0] * len(combined)
    tie_sum = 0
    index = 0
    while index < len(combined):
        end = index + 1
        while end < len(combined) and combined[end][0] == combined[index][0]:
            end += 1
        rank = (index + 1 + end) / 2
        for cursor in range(index, end):
            ranks[cursor] = rank
        tie = end - index
        tie_sum += tie**3 - tie
        index = end
    rank_a = sum(rank for rank, (_, group) in zip(ranks, combined) if group == 0)
    n_a, n_b = len(a), len(b)
    u = rank_a - n_a * (n_a + 1) / 2
    total = n_a + n_b
    variance = n_a * n_b / 12 * (total + 1 - tie_sum / (total * (total - 1)))
    z = (u - n_a * n_b / 2) / math.sqrt(variance)
    return {"u": u, "z": z, "p_two_sided": math.erfc(abs(z) / math.sqrt(2))}


def parse_report(output: str) -> dict[str, object]:
    for line in output.splitlines():
        if line.startswith(PREFIX):
            return json.loads(line[len(PREFIX):])
    raise RuntimeError("benchmark report marker missing")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", required=True, help="node executable")
    parser.add_argument("--bun", required=True, help="bun executable")
    parser.add_argument(
        "--bundle",
        action="append",
        required=True,
        help="label=/path/to/bundle.js (repeatable)",
    )
    parser.add_argument("--repetitions", type=int, default=15)
    parser.add_argument("--seed", type=int, default=4)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    bundles = dict(item.split("=", 1) for item in args.bundle)
    runtimes = {"node": args.node, "bun": args.bun}
    cases = [
        (runtime, label)
        for runtime in runtimes
        for label in bundles
    ]
    rng = random.Random(args.seed)
    rows: list[dict[str, object]] = []

    for repetition in range(args.repetitions):
        order = list(cases)
        rng.shuffle(order)
        for runtime, label in order:
            process = subprocess.run(
                [runtimes[runtime], bundles[label]],
                capture_output=True,
                text=True,
                env=os.environ.copy(),
            )
            if process.returncode:
                raise RuntimeError(
                    f"{runtime}/{label} repetition {repetition} failed: "
                    f"{process.stderr[-1000:]}"
                )
            report = parse_report(process.stdout)
            timings = report["timings"]
            multi_key = next(key for key in MULTI_KEYS if key in timings)
            row = {
                "repetition": repetition,
                "runtime": runtime,
                "bundle": label,
                "multi_us": timings[multi_key]["medianUs"],
                "timings_us": {
                    key: value["medianUs"] for key, value in timings.items()
                },
                "fingerprints": report["fingerprints"],
            }
            rows.append(row)
            print(
                f"{repetition:02d} {runtime:4} {label:18} "
                f"multi={row['multi_us']:9.3f} us "
                f"fp={report['fingerprints'][multi_key]}",
                flush=True,
            )

    grouped: dict[str, list[float]] = {}
    for row in rows:
        grouped.setdefault(f"{row['runtime']}/{row['bundle']}", []).append(
            float(row["multi_us"])
        )
    summaries = {
        key: {
            "n": len(values),
            "median_us": statistics.median(values),
            "p25_us": percentile(values, 25),
            "p75_us": percentile(values, 75),
        }
        for key, values in grouped.items()
    }
    comparisons = {}
    for label in bundles:
        node_values = grouped[f"node/{label}"]
        bun_values = grouped[f"bun/{label}"]
        node_median = statistics.median(node_values)
        bun_median = statistics.median(bun_values)
        comparisons[label] = {
            "node_median_us": node_median,
            "bun_median_us": bun_median,
            "bun_over_node": bun_median / node_median,
            "mann_whitney": mann_whitney(bun_values, node_values),
        }

    result = {
        "node": args.node,
        "bun": args.bun,
        "bundles": {
            label: subprocess.check_output(
                ["sha256sum", path], text=True
            ).split()[0]
            for label, path in bundles.items()
        },
        "repetitions": args.repetitions,
        "seed": args.seed,
        "summaries": summaries,
        "comparisons": comparisons,
        "raw": rows,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"summaries": summaries, "comparisons": comparisons}, indent=2))
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
