#!/usr/bin/env python3
"""Repeat PR #12's 3+3 blocked protocol, alternating block direction."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import statistics
import subprocess
from pathlib import Path

PERF_SCRIPT = Path(__file__).with_name("run-fms-real-workload.py")
SPEC = importlib.util.spec_from_file_location("run_fms_real_workload", PERF_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {PERF_SCRIPT}")
PERF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PERF)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bun", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rows = []
    trials = []
    for trial in range(args.trials):
        order = ["default", "global-1"]
        if trial % 2:
            order.reverse()
        medians = {}
        for condition in order:
            samples = []
            for sample in range(3):
                env = os.environ.copy()
                if condition == "global-1":
                    env["BUN_JSC_osrExitCountForReoptimization"] = "1"
                process = subprocess.run(
                    [args.bun, args.bundle],
                    capture_output=True,
                    text=True,
                    env=env,
                )
                if process.returncode:
                    raise RuntimeError(process.stderr[-1000:])
                report = PERF.parse_report(process.stdout)
                value = report["timings"]["i4-multi-only"]["medianUs"]
                samples.append(value)
                rows.append(
                    {
                        "trial": trial,
                        "block_position": order.index(condition),
                        "condition": condition,
                        "sample": sample,
                        "median_us": value,
                        "fingerprint": report["fingerprints"]["i4-multi-only"],
                    }
                )
            medians[condition] = statistics.median(samples)
        delta = medians["global-1"] - medians["default"]
        trials.append(
            {
                "trial": trial,
                "order": order,
                "default_median_us": medians["default"],
                "global_1_median_us": medians["global-1"],
                "delta_us": delta,
                "delta_percent": 100 * delta / medians["default"],
            }
        )
        print(json.dumps(trials[-1]), flush=True)

    result = {
        "protocol": "PR12 exact 3-process blocks; direction alternated by trial",
        "trials": trials,
        "raw": rows,
        "median_trial_delta_percent": statistics.median(
            trial["delta_percent"] for trial in trials
        ),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
