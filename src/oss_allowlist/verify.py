"""Check every downloaded file against the digest its upstream published."""

from __future__ import annotations

import logging
from pathlib import Path

from . import manifest

log = logging.getLogger(__name__)


def verify(dist: Path) -> list[str]:
    """Return a list of problems; empty means every file verified."""
    problems = []
    for mf in manifest.load(dist):
        path = dist / mf.filename
        if not path.exists():
            problems.append(f"{mf.filename}: missing from {dist}")
            continue
        if not mf.expected:
            problems.append(f"{mf.filename}: upstream published no digest to verify against")
            continue
        for algorithm, want in mf.expected.items():
            got = manifest.file_digest(path, algorithm)
            if got != want.lower():
                problems.append(f"{mf.filename}: {algorithm} mismatch (expected {want}, got {got})")
            else:
                log.info("%s: %s ok %s", mf.filename, algorithm, got)
    return problems
