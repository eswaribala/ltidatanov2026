#!/usr/bin/env python3
"""Print a Jaeger trace as an indented tree (text waterfall).

Usage: python3 trace-tree.py <trace_id> [jaeger_url]
Columns: start offset (ms), duration (ms), self time (ms), status, service: span
"""

import json
import sys
import urllib.request

if len(sys.argv) < 2:
    sys.exit("Usage: python3 trace-tree.py <trace_id> [jaeger_url]")

tid = sys.argv[1]
base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:16686"
url = base_url.rstrip("/") + f"/api/traces/{tid}"

with urllib.request.urlopen(url) as response:
    data = json.load(response)["data"][0]

procs = {k: v["serviceName"] for k, v in data["processes"].items()}
spans = {s["spanID"]: s for s in data["spans"]}
kids = {}

for s in data["spans"]:
    parent = next(
        (
            r["spanID"]
            for r in s.get("references", [])
            if r["refType"] == "CHILD_OF"
        ),
        None,
    )
    kids.setdefault(parent if parent in spans else None, []).append(s)

t0 = min(s["startTime"] for s in data["spans"])


def covered(children):
    """Return union of child span intervals, in microseconds."""
    intervals = sorted(
        (c["startTime"], c["startTime"] + c["duration"])
        for c in children
    )
    total = 0
    end = None

    for a, b in intervals:
        if end is None or a > end:
            total += b - a
            end = b
        elif b > end:
            total += b - end
            end = b

    return total


print(f"Trace {tid}: {len(spans)} spans, {len(set(procs.values()))} services")
print(f"{'start':>7} {'dur':>7} {'self':>7} status span")


def walk(s, depth):
    children = sorted(
        kids.get(s["spanID"], []),
        key=lambda c: c["startTime"],
    )
    err = any(
        t["key"] == "error" and t["value"] in (True, "true")
        for t in s.get("tags", [])
    )

    print(
        f"{(s['startTime'] - t0) / 1000:7.0f} "
        f"{s['duration'] / 1000:7.0f} "
        f"{(s['duration'] - covered(children)) / 1000:7.0f} "
        f"{'ERROR ' if err else 'ok    '} "
        f"{'  ' * depth}{procs[s['processID']]}: {s['operationName']}"
    )

    for child in children:
        walk(child, depth + 1)


for root in sorted(kids.get(None, []), key=lambda c: c["startTime"]):
    walk(root, 0)
