#!/usr/bin/env python3
"""Interleaved transition-trajectory benchmark for the exact FMS workload."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import statistics
import subprocess
from pathlib import Path

PERF_SCRIPT = Path(__file__).with_name("run-fms-real-workload.py")
SPEC = importlib.util.spec_from_file_location("run_fms_real_workload", PERF_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {PERF_SCRIPT}")
PERF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PERF)


def group(values: list[float], start: int, end: int) -> float:
    return statistics.mean(values[start - 1 : end])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("bun", "jsc"), required=True)
    parser.add_argument("--executable", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--repetitions", type=int, default=20)
    parser.add_argument("--seed", type=int, default=40477)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cases = PERF.conditions(args.mode, args.executable)
    rng = random.Random(args.seed)
    rows = []
    for repetition in range(args.repetitions):
        order = list(cases)
        rng.shuffle(order)
        for position, condition in enumerate(order):
            command, additions = cases[condition]
            env = os.environ.copy()
            env.update(additions)
            process = subprocess.run(
                [*command, args.bundle],
                capture_output=True,
                text=True,
                env=env,
            )
            if process.returncode:
                raise RuntimeError(process.stderr[-1000:])
            report = PERF.parse_report(process.stdout)
            first = report["transition"]["firstSearchesUs"]
            row = {
                "repetition": repetition,
                "position": position,
                "condition": condition,
                "search-1": first[0],
                "search-2": first[1],
                "searches-3-4": group(first, 3, 4),
                "searches-5-8": group(first, 5, 8),
                "searches-9-16": group(first, 9, 16),
                "searches-17-32": group(first, 17, 32),
                "settled": report["timings"]["i4-multi-only"]["medianUs"],
                "fingerprint": report["fingerprints"]["i4-multi-only"],
            }
            rows.append(row)
            print(
                f"{repetition:02d}.{position} {condition:8} "
                f"s1={row['search-1']:.1f} settled={row['settled']:.1f}",
                flush=True,
            )

    stages = (
        "search-1",
        "search-2",
        "searches-3-4",
        "searches-5-8",
        "searches-9-16",
        "searches-17-32",
        "settled",
    )
    summaries = {}
    for condition in cases:
        summaries[condition] = {}
        for stage_index, stage in enumerate(stages):
            values = [
                float(row[stage])
                for row in rows
                if row["condition"] == condition
            ]
            summaries[condition][stage] = {
                "median_us": statistics.median(values),
                "median_ci95_us": PERF.bootstrap_median_ci(
                    values, args.seed + stage_index
                ),
            }

    result = {
        "mode": args.mode,
        "bundle": args.bundle,
        "bundle_sha256": subprocess.check_output(
            ["sha256sum", args.bundle], text=True
        ).split()[0],
        "repetitions": args.repetitions,
        "fingerprints": sorted({row["fingerprint"] for row in rows}),
        "summaries": summaries,
        "raw": rows,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(summaries, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
