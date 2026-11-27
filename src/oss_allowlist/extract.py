"""Find catalog entries added between a base git ref and the working tree."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from .models import Entry, entry_to_dict, parse_catalog

log = logging.getLogger(__name__)

CATALOGS: dict[str, str] = {
    "python": "data/python.yaml",
    "maven": "data/maven.yaml",
}


def added_entries(base_text: str, head_text: str, ecosystem: str) -> list[Entry]:
    """Entries in ``head_text`` that are not in ``base_text``, in head order."""
    before = set(parse_catalog(base_text, ecosystem))
    return [e for e in parse_catalog(head_text, ecosystem) if e not in before]


def read_at_ref(repo: Path, ref: str, path: str) -> str:
    """Contents of ``path`` at ``ref``, or "" if the file did not exist there."""
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout
    if "does not exist" in result.stderr or "exists on disk, but not in" in result.stderr:
        return ""
    raise RuntimeError(f"git show {ref}:{path} failed: {result.stderr.strip()}")


def merge_base(repo: Path, base: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "merge-base", base, "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def extract(repo: Path, base: str) -> list[Entry]:
    ref = merge_base(repo, base)
    added: list[Entry] = []
    for ecosystem, rel in CATALOGS.items():
        head = repo / rel
        head_text = head.read_text() if head.exists() else ""
        added += added_entries(read_at_ref(repo, ref, rel), head_text, ecosystem)
    return added


def run(repo: Path, base: str, output: Path) -> int:
    added = extract(repo, base)
    output.write_text(json.dumps([entry_to_dict(e) for e in added], indent=2) + "\n")
    for e in added:
        log.info("added %s %s", e.type, e.coordinate)
    log.info("%d new entr%s written to %s", len(added), "y" if len(added) == 1 else "ies", output)
    return len(added)
