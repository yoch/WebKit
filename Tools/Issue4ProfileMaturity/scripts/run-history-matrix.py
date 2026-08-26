#!/usr/bin/env python3
"""Interleaved fresh-process history matrix for FrozenMiniSearch issue #4."""

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
            return json.loads(line[len(PREFIX) :])
    raise RuntimeError("benchmark report marker missing:\n" + output[-1000:])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, help="name, e.g. node / bun / d8 / jsc")
    parser.add_argument("--executable", required=True)
    parser.add_argument("--flag", action="append", default=[], help="extra CLI flag")
    parser.add_argument("--env", action="append", default=[], help="KEY=VALUE")
    parser.add_argument(
        "--bundle",
        action="append",
        required=True,
        help="history-label=/path/to/bundle.js",
    )
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument("--seed", type=int, default=4)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    bundles = dict(item.split("=", 1) for item in args.bundle)
    extra_env = dict(item.split("=", 1) for item in args.env)
    rng = random.Random(args.seed)
    labels = list(bundles)
    rows: list[dict[str, object]] = []

    for repetition in range(args.repetitions):
        order = labels[:]
        rng.shuffle(order)
        for label in order:
            env = os.environ.copy()
            env.update(extra_env)
            process = subprocess.run(
                [args.executable, *args.flag, bundles[label]],
                capture_output=True,
                text=True,
                env=env,
            )
            if process.returncode:
                raise RuntimeError(
                    f"{args.runtime}/{label} rep {repetition} failed "
                    f"(code {process.returncode}): {process.stderr[-1500:]}"
                )
            report = parse_report(process.stdout)
            timings = report["timings"]
            if "resident-multi" not in timings and "i4-multi-only" not in timings:
                raise RuntimeError(f"no multi timing in {label}: {list(timings)}")
            multi_key = (
                "resident-multi" if "resident-multi" in timings else "i4-multi-only"
            )
            row = {
                "repetition": repetition,
                "runtime": args.runtime,
                "history": label,
                "multi_us": timings[multi_key]["medianUs"],
                "timings_us": {key: value["medianUs"] for key, value in timings.items()},
                "fingerprints": report["fingerprints"],
                "fingerprint": report["fingerprints"][multi_key],
            }
            rows.append(row)
            print(
                f"{repetition:02d} {args.runtime:4} {label:12} "
                f"multi={row['multi_us']:9.3f} us fp={row['fingerprint']}",
                flush=True,
            )

    grouped = {
        label: [float(row["multi_us"]) for row in rows if row["history"] == label]
        for label in labels
    }
    summaries = {
        label: {
            "n": len(values),
            "median_us": statistics.median(values),
            "p25_us": percentile(values, 25),
            "p75_us": percentile(values, 75),
            "mean_us": statistics.mean(values),
        }
        for label, values in grouped.items()
    }
    reference = labels[0]
    comparisons = {}
    for label in labels[1:]:
        ref_median = statistics.median(grouped[reference])
        median = statistics.median(grouped[label])
        comparisons[f"{label}-vs-{reference}"] = {
            "delta_us": median - ref_median,
            "delta_percent": 100 * (median - ref_median) / ref_median,
            "mann_whitney": mann_whitney(grouped[label], grouped[reference]),
        }

    result = {
        "runtime": args.runtime,
        "executable": args.executable,
        "flags": args.flag,
        "env": extra_env,
        "bundles": {
            label: subprocess.check_output(["sha256sum", path], text=True).split()[0]
            for label, path in bundles.items()
        },
        "repetitions": args.repetitions,
        "seed": args.seed,
        "fingerprints": sorted({str(row["fingerprint"]) for row in rows}),
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
