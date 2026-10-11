#!/usr/bin/env python3
"""Run deterministic, duration-balanced pytest shards and verify complete coverage.

The ordinary ``python -m pytest`` command remains unchanged. Every shard collects
the full suite, keeps complete modules together, and records a coverage receipt.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "scripts" / "ci-test-durations.json"


def fingerprint(nodeids):
    return hashlib.sha256(json.dumps(sorted(nodeids), ensure_ascii=True).encode()).hexdigest()


def partition(nodeids, count, weights):
    """Greedy module scheduling; ties are resolved by path and shard number."""
    if count < 1 or len(nodeids) != len(set(nodeids)):
        raise ValueError("Invalid shard count or duplicate collected node IDs")
    modules = defaultdict(list)
    for nodeid in nodeids:
        modules[nodeid.split("::", 1)[0]].append(nodeid)
    if len(modules) < count:
        raise ValueError("Fewer collected modules than shards")
    historical = weights.get("modules", {})
    total_cases = sum(entry["cases"] for entry in historical.values())
    average = sum(entry["seconds"] for entry in historical.values()) / max(total_cases, 1)

    def cost(path):
        old = historical.get(path, {})
        per_case = old.get("seconds", average) / max(old.get("cases", 1), 1)
        return max(per_case, 0.001) * len(modules[path])

    groups = [{"index": i + 1, "nodeids": [], "estimated_seconds": 0.0} for i in range(count)]
    for path in sorted(modules, key=lambda p: (-cost(p), p)):
        group = min(groups, key=lambda g: (g["estimated_seconds"], len(g["nodeids"]), g["index"]))
        group["nodeids"].extend(sorted(modules[path]))
        group["estimated_seconds"] += cost(path)
    for group in groups:
        group["nodeids"].sort()
        group["estimated_seconds"] = round(group["estimated_seconds"], 3)
    return groups


def verify(receipts):
    """Fail closed on missing shards, mismatched collections, repeats or omissions."""
    if not receipts:
        raise ValueError("No shard receipts")
    first = receipts[0]
    if first.get("schema") != 2:
        raise ValueError("Shard receipts must identify the tests actually executed")
    count = first["shard_count"]
    if len(receipts) != count or sorted(r["index"] for r in receipts) != list(range(1, count + 1)):
        raise ValueError("Missing or duplicate shard receipts")
    for receipt in receipts:
        if receipt.get("exit_code") != 0:
            raise ValueError("A shard did not complete successfully")
        for key in ("schema", "shard_count", "collection_count", "collection_sha256"):
            if receipt[key] != first[key]:
                raise ValueError(f"Shard collections disagree: {key}")
        if receipt.get("executed_count") != len(receipt["nodeids"]):
            raise ValueError("A shard did not execute its complete selection")
        if receipt.get("executed_sha256") != fingerprint(receipt["nodeids"]):
            raise ValueError("Executed tests differ from the shard selection")
    combined = [nodeid for receipt in receipts for nodeid in receipt["nodeids"]]
    if len(combined) != len(set(combined)):
        raise ValueError("Duplicate tests across shards")
    if len(combined) != first["collection_count"] or fingerprint(combined) != first["collection_sha256"]:
        raise ValueError("Shard union does not equal the full collected suite")
    return {"tests": len(combined), "shards": count, "collection_sha256": fingerprint(combined)}


class ShardPlugin:
    def __init__(self, args):
        self.args = args
        self.data = None
        self.executed = Counter()

    def pytest_collection_modifyitems(self, config, items):
        nodeids = [item.nodeid for item in items]
        groups = partition(nodeids, self.args.count, json.loads(WEIGHTS.read_text()))
        self.data = {"schema": 2, "shard_count": self.args.count,
                     "collection_count": len(nodeids), "collection_sha256": fingerprint(nodeids)}
        if self.args.plan:
            self.data["groups"] = groups
            return
        group = groups[self.args.index - 1]
        self.data.update(group)
        keep = set(group["nodeids"])
        removed = [item for item in items if item.nodeid not in keep]
        items[:] = [item for item in items if item.nodeid in keep]
        config.hook.pytest_deselected(items=removed)

    def pytest_runtest_logreport(self, report):
        # Successful, failed and skipped calls all count; a setup failure/skip
        # has no call report and is counted here instead.
        if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
            self.executed[report.nodeid] += 1

    def pytest_sessionfinish(self, session, exitstatus):
        if self.data is not None:
            self.data["exit_code"] = int(exitstatus)
            self.data["executed_count"] = sum(self.executed.values())
            # Include identities and multiplicity: an extra execution must not
            # compensate for an omitted test merely because totals agree.
            self.data["executed_sha256"] = fingerprint(list(self.executed.elements()))
            self.args.output.parent.mkdir(parents=True, exist_ok=True)
            self.args.output.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--index", type=int)
    parser.add_argument("--plan", action="store_true", help="Collect only and write every assignment")
    parser.add_argument("--output", type=Path, default=ROOT / "out" / "pytest-plan.json")
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--verify", nargs="+", type=Path, metavar="RECEIPT")
    args = parser.parse_args(argv)
    if args.verify:
        try:
            result = verify([json.loads(path.read_text()) for path in args.verify])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            parser.exit(1, f"Coverage verification failed: {exc}\n")
        print(json.dumps(result, indent=2))
        return 0
    if args.count < 1 or (not args.plan and (args.index is None or not 1 <= args.index <= args.count)):
        parser.error("Use --plan or an --index between 1 and --count")
    # Tests and application modules resolve from this checkout, even when the
    # script is called using an absolute path from another directory.
    import os
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    import pytest
    pytest_args = [str(ROOT / "tests"), "-q"]
    if args.plan:
        pytest_args.append("--collect-only")
    if args.junit:
        pytest_args.append(f"--junitxml={args.junit.resolve()}")
    return int(pytest.main(pytest_args, plugins=[ShardPlugin(args)]))


if __name__ == "__main__":
    raise SystemExit(main())
