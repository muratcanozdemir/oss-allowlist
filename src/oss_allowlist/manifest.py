"""The dist/manifest.json that ties downloaded files to their coordinates and digests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .models import Entry, entry_from_json, entry_to_dict

MANIFEST_NAME = "manifest.json"
REPORTS_DIR = "reports"


@dataclass
class ManifestFile:
    """One downloaded file."""

    filename: str
    entry: Entry
    kind: str  # wheel, sdist, jar, pom
    url: str
    expected: dict[str, str] = field(default_factory=dict)  # algorithm -> hex digest

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["entry"] = entry_to_dict(self.entry)
        return data

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> ManifestFile:
        return cls(
            filename=raw["filename"],
            entry=entry_from_json(raw["entry"]),
            kind=raw["kind"],
            url=raw["url"],
            expected=dict(raw.get("expected", {})),
        )

    @property
    def scannable(self) -> bool:
        return self.kind != "pom"


def save(dist: Path, files: list[ManifestFile]) -> Path:
    path = dist / MANIFEST_NAME
    path.write_text(json.dumps([f.to_json() for f in files], indent=2) + "\n")
    return path


def load(dist: Path) -> list[ManifestFile]:
    path = dist / MANIFEST_NAME
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: run 'oss-allowlist fetch' first")
    return [ManifestFile.from_json(raw) for raw in json.loads(path.read_text())]


def sbom_path(dist: Path, filename: str) -> Path:
    return dist / REPORTS_DIR / f"{filename}.sbom.json"


def vuln_path(dist: Path, filename: str) -> Path:
    return dist / REPORTS_DIR / f"{filename}.vuln.json"


def file_digest(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        while chunk := f.read(1 << 16):
            h.update(chunk)
    return h.hexdigest()
