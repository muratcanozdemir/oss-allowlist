"""Allowlist entries and the YAML catalogs that declare them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


class CatalogError(ValueError):
    """A catalog file or entry is malformed."""


@dataclass(frozen=True)
class PythonPackage:
    package: str
    version: str
    type: str = "python"

    @property
    def coordinate(self) -> str:
        return f"{self.package}=={self.version}"


@dataclass(frozen=True)
class MavenArtifact:
    group: str
    artifact: str
    version: str
    type: str = "maven"

    @property
    def coordinate(self) -> str:
        return f"{self.group}:{self.artifact}:{self.version}"

    @property
    def path(self) -> str:
        """Directory of this artifact in the standard Maven repository layout."""
        return f"{self.group.replace('.', '/')}/{self.artifact}/{self.version}"


Entry = PythonPackage | MavenArtifact

_FIELDS: dict[str, tuple[str, ...]] = {
    "python": ("package", "version"),
    "maven": ("group", "artifact", "version"),
}


def entry_from_dict(raw: Any, ecosystem: str) -> Entry:
    """Build an entry for ``ecosystem`` ("python" or "maven") from a mapping."""
    if ecosystem not in _FIELDS:
        raise CatalogError(f"unknown ecosystem {ecosystem!r}")
    if not isinstance(raw, dict):
        raise CatalogError(f"{ecosystem} entry must be a mapping, got {raw!r}")
    fields = _FIELDS[ecosystem]
    missing = [f for f in fields if f not in raw]
    if missing:
        raise CatalogError(f"{ecosystem} entry {raw!r} is missing {', '.join(missing)}")
    extra = set(raw) - set(fields) - {"type"}
    if extra:
        raise CatalogError(f"{ecosystem} entry {raw!r} has unknown keys {', '.join(sorted(extra))}")
    values = {}
    for f in fields:
        value = raw[f]
        # YAML turns 1.10 into the float 1.1: refuse anything that isn't a string.
        if not isinstance(value, str) or not value.strip():
            raise CatalogError(
                f"{ecosystem} entry {raw!r}: {f} must be a non-empty string (quote versions in YAML)"
            )
        values[f] = value.strip()
    if ecosystem == "python":
        return PythonPackage(**values)
    return MavenArtifact(**values)


def entry_to_dict(entry: Entry) -> dict[str, str]:
    if isinstance(entry, PythonPackage):
        return {"type": "python", "package": entry.package, "version": entry.version}
    return {
        "type": "maven",
        "group": entry.group,
        "artifact": entry.artifact,
        "version": entry.version,
    }


def entry_from_json(raw: dict[str, Any]) -> Entry:
    """Inverse of :func:`entry_to_dict`."""
    return entry_from_dict(raw, raw.get("type", ""))


def parse_catalog(text: str, ecosystem: str) -> list[Entry]:
    """Parse a catalog document (``packages:`` list). Empty text is an empty catalog."""
    try:
        doc = yaml.safe_load(text) if text.strip() else None
    except yaml.YAMLError as exc:
        raise CatalogError(f"invalid YAML: {exc}") from exc
    if doc is None:
        return []
    packages = doc.get("packages") if isinstance(doc, dict) else None
    if not isinstance(doc, dict) or not isinstance(packages or [], list):
        raise CatalogError("catalog must be a mapping with a 'packages' list")
    entries = [entry_from_dict(item, ecosystem) for item in packages or []]
    seen: set[Entry] = set()
    for e in entries:
        if e in seen:
            raise CatalogError(f"duplicate entry {e.coordinate}")
        seen.add(e)
    return entries
