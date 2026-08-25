#!/usr/bin/env python3
"""Summarize chronological JSC compile/OSR events from FMS diagnostic logs."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

COMPILE = re.compile(
    r"Optimized (?P<function>[^#\s]+)#.* using (?P<tier>DFG|FTL).* "
    r"in (?P<milliseconds>[0-9.]+) ms"
)
EXIT = re.compile(
    r"Speculation failure in (?P<function>[^#\s]+)#.*"
    r"bc#(?P<bytecode>\d+), (?P<kind>\w+)\).*"
    r"reoptimizationRetryCounter = (?P<retry>\d+).*"
    r"osrExitCounter = (?P<aggregate>\d+)"
)
FOCUS = {
    "scorePostingDoc",
    "aggregateSegmentPostingList",
    "executeQueryInternal",
    "executeQuerySpecInternal",
}


def parse(path: Path) -> dict[str, object]:
    events = []
    sites: Counter[tuple[str, int, str]] = Counter()
    functions: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    compiles: Counter[tuple[str, str]] = Counter()
    for line_number, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        compile_match = COMPILE.search(line)
        if compile_match:
            event = {
                "line": line_number,
                "event": "compile",
                "function": compile_match.group("function"),
                "tier": compile_match.group("tier"),
                "milliseconds": float(compile_match.group("milliseconds")),
            }
            events.append(event)
            compiles[(event["function"], event["tier"])] += 1
            continue
        exit_match = EXIT.search(line)
        if not exit_match:
            continue
        event = {
            "line": line_number,
            "event": "exit",
            "function": exit_match.group("function"),
            "bytecode": int(exit_match.group("bytecode")),
            "kind": exit_match.group("kind"),
            "retry": int(exit_match.group("retry")),
            "aggregate_before": int(exit_match.group("aggregate")),
        }
        events.append(event)
        key = (event["function"], event["bytecode"], event["kind"])
        sites[key] += 1
        functions[event["function"]] += 1
        kinds[event["kind"]] += 1

    focus_events = [event for event in events if event.get("function") in FOCUS]
    return {
        "log": str(path),
        "exit_count": sum(kinds.values()),
        "exit_kinds": dict(kinds.most_common()),
        "top_exit_functions": dict(functions.most_common(20)),
        "top_exit_sites": [
            {
                "function": function,
                "bytecode": bytecode,
                "kind": kind,
                "count": count,
            }
            for (function, bytecode, kind), count in sites.most_common(30)
        ],
        "compile_counts": [
            {"function": function, "tier": tier, "count": count}
            for (function, tier), count in compiles.most_common()
            if function in FOCUS
        ],
        "focus_timeline": focus_events,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log",
        action="append",
        required=True,
        help="condition=/path/to/log; repeat for each condition",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = {}
    for item in args.log:
        condition, raw_path = item.split("=", 1)
        result[condition] = parse(Path(raw_path))
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
