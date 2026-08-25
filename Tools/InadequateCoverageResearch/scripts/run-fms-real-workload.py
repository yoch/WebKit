#!/usr/bin/env python3
"""Interleaved process-level benchmarks for the exact FMS issue4 workload."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import subprocess
import time
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


def bootstrap_median_ci(values: list[float], seed: int) -> list[float]:
    rng = random.Random(seed)
    medians = [
        statistics.median(rng.choices(values, k=len(values)))
        for _ in range(10_000)
    ]
    medians.sort()
    return [percentile(medians, 2.5), percentile(medians, 97.5)]


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
    rank_a = sum(
        rank for rank, (_, group) in zip(ranks, combined) if group == 0
    )
    n_a = len(a)
    n_b = len(b)
    u = rank_a - n_a * (n_a + 1) / 2
    mean = n_a * n_b / 2
    total = n_a + n_b
    variance = n_a * n_b / 12 * (
        total + 1 - tie_sum / (total * (total - 1))
    )
    z = (u - mean) / math.sqrt(variance)
    return {"u": u, "z": z, "p_two_sided": math.erfc(abs(z) / math.sqrt(2))}


def summary(values: list[float], seed: int) -> dict[str, object]:
    return {
        "n": len(values),
        "median_us": statistics.median(values),
        "p25_us": percentile(values, 25),
        "p75_us": percentile(values, 75),
        "p90_us": percentile(values, 90),
        "p95_us": percentile(values, 95),
        "mean_us": statistics.mean(values),
        "median_ci95_us": bootstrap_median_ci(values, seed),
    }


def parse_report(output: str) -> dict[str, object]:
    for line in output.splitlines():
        if line.startswith(PREFIX):
            return json.loads(line[len(PREFIX) :])
    raise RuntimeError("benchmark report marker missing")


def conditions(mode: str, executable: str) -> dict[str, tuple[list[str], dict[str, str]]]:
    if mode == "bun":
        return {
            "default": ([executable], {}),
            "global-1": (
                [executable],
                {"BUN_JSC_osrExitCountForReoptimization": "1"},
            ),
        }
    if mode == "jsc":
        disabled = "--osrExitCountForReoptimizationFromInadequateCoverage=1000000"
        return {
            "P0": ([executable, disabled], {}),
            "P5": ([executable], {}),
            "G1": ([executable, "--osrExitCountForReoptimization=1", disabled], {}),
            "G1P5": ([executable, "--osrExitCountForReoptimization=1"], {}),
        }
    raise ValueError(mode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("bun", "jsc"), required=True)
    parser.add_argument("--executable", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument("--seed", type=int, default=40477)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cases = conditions(args.mode, args.executable)
    rng = random.Random(args.seed)
    rows: list[dict[str, object]] = []

    for repetition in range(args.repetitions):
        order = list(cases)
        rng.shuffle(order)
        for condition in order:
            command, additions = cases[condition]
            env = os.environ.copy()
            env.update(additions)
            started = time.perf_counter()
            process = subprocess.run(
                [*command, args.bundle],
                capture_output=True,
                text=True,
                env=env,
            )
            wall_seconds = time.perf_counter() - started
            if process.returncode:
                raise RuntimeError(
                    f"{condition} repetition {repetition} failed: "
                    f"{process.stderr[-1000:]}"
                )
            report = parse_report(process.stdout)
            timing = report["timings"]["i4-multi-only"]
            row = {
                "repetition": repetition,
                "position": order.index(condition),
                "condition": condition,
                "median_us": timing["medianUs"],
                "min_us": timing["minUs"],
                "max_us": timing["maxUs"],
                "batch": timing["batch"],
                "samples": timing["samples"],
                "fingerprint": report["fingerprints"]["i4-multi-only"],
                "sink": report["sink"],
                "documents": report["corpus"]["documents"],
                "terms": report["corpus"]["terms"],
                "wall_seconds": wall_seconds,
            }
            rows.append(row)
            print(
                f"{repetition:02d}.{row['position']} {condition:8} "
                f"{row['median_us']:.3f} us fp={row['fingerprint']}",
                flush=True,
            )

    grouped = {
        condition: [
            float(row["median_us"])
            for row in rows
            if row["condition"] == condition
        ]
        for condition in cases
    }
    summaries = {
        condition: summary(values, args.seed + index)
        for index, (condition, values) in enumerate(grouped.items())
    }
    comparisons = {}
    reference = "default" if args.mode == "bun" else "P0"
    reference_values = grouped[reference]
    for condition, values in grouped.items():
        if condition == reference:
            continue
        ref_median = statistics.median(reference_values)
        median = statistics.median(values)
        comparisons[f"{condition}-vs-{reference}"] = {
            "delta_us": median - ref_median,
            "delta_percent": 100 * (median - ref_median) / ref_median,
            "mann_whitney": mann_whitney(values, reference_values),
        }

    fingerprints = sorted({str(row["fingerprint"]) for row in rows})
    result = {
        "mode": args.mode,
        "executable": args.executable,
        "bundle": args.bundle,
        "bundle_sha256": subprocess.check_output(
            ["sha256sum", args.bundle], text=True
        ).split()[0],
        "repetitions": args.repetitions,
        "seed": args.seed,
        "fingerprints": fingerprints,
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
