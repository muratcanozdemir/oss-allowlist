"""Block artifacts whose Grype report has findings at or above a severity threshold."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from . import manifest

SEVERITIES = ["negligible", "low", "medium", "high", "critical"]


def rank(severity: str) -> int:
    try:
        return SEVERITIES.index(severity.strip().lower())
    except ValueError:
        return -1  # "Unknown" and anything unrecognized never blocks on its own


def violations(report: dict[str, Any], fail_on: str, ignore: Iterable[str] = ()) -> list[str]:
    threshold = rank(fail_on)
    if threshold < 0:
        raise ValueError(f"unknown severity {fail_on!r}; choose from {', '.join(SEVERITIES)}")
    ignored = {i.upper() for i in ignore}
    found = []
    for match in report.get("matches", []):
        v = match.get("vulnerability", {})
        vid = v.get("id", "?")
        if vid.upper() in ignored:
            continue
        sev = v.get("severity", "Unknown")
        if rank(sev) >= threshold:
            pkg = match.get("artifact", {})
            found.append(f"{vid} ({sev}) in {pkg.get('name', '?')} {pkg.get('version', '')}".rstrip())
    return sorted(set(found))


def evaluate(dist: Path, fail_on: str = "critical", ignore: Iterable[str] = ()) -> dict[str, list[str]]:
    """Map each blocked file to its problems; empty means the intake may proceed."""
    ignore = list(ignore)
    blocked: dict[str, list[str]] = {}
    for mf in manifest.load(dist):
        if not mf.scannable:
            continue
        path = manifest.vuln_path(dist, mf.filename)
        if not path.exists():
            blocked[mf.filename] = ["no vulnerability report: run 'oss-allowlist vuln' first"]
            continue
        problems = violations(json.loads(path.read_text()), fail_on, ignore)
        if problems:
            blocked[mf.filename] = problems
    return blocked
