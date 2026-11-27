from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from oss_allowlist import manifest
from oss_allowlist.manifest import ManifestFile
from oss_allowlist.models import MavenArtifact, PythonPackage


@dataclass
class FakeResponse:
    status_code: int = 200
    content: bytes = b""
    payload: Any = None

    @property
    def text(self) -> str:
        return self.content.decode()

    def json(self) -> Any:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size: int = 1) -> Any:
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i : i + chunk_size]


@dataclass
class FakeSession:
    """Serves canned responses by URL; anything else is a 404."""

    routes: dict[str, FakeResponse] = field(default_factory=dict)
    gets: list[str] = field(default_factory=list)
    puts: list[dict[str, Any]] = field(default_factory=list)
    put_status: int = 201

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.gets.append(url)
        return self.routes.get(url, FakeResponse(status_code=404))

    def put(self, url: str, data: Any = None, **kwargs: Any) -> FakeResponse:
        self.puts.append({"url": url, "body": data.read(), **kwargs})
        return FakeResponse(status_code=self.put_status, content=b"nope")


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


REQUESTS = PythonPackage("requests", "2.31.0")
GUAVA = MavenArtifact("com.google.guava", "guava", "32.1.2")


@pytest.fixture
def populated_dist(tmp_path: Path) -> Path:
    """A dist dir with a wheel, a jar and a pom, all with correct expected digests."""
    dist = tmp_path / "dist"
    dist.mkdir()
    blobs = {
        "requests-2.31.0-py3-none-any.whl": (REQUESTS, "wheel", b"wheel-bytes"),
        "guava-32.1.2.jar": (GUAVA, "jar", b"jar-bytes"),
        "guava-32.1.2.pom": (GUAVA, "pom", b"<project/>"),
    }
    files = []
    for name, (entry, kind, data) in blobs.items():
        (dist / name).write_bytes(data)
        files.append(
            ManifestFile(name, entry, kind, f"https://example.test/{name}", {"sha256": sha256(data)})
        )
    manifest.save(dist, files)
    return dist
