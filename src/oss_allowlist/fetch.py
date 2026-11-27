"""Download artifacts and the digests their upstream repositories publish for them."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from . import manifest
from .manifest import ManifestFile
from .models import Entry, MavenArtifact, PythonPackage, entry_from_json

log = logging.getLogger(__name__)

DEFAULT_PYPI_URL = "https://pypi.org"
DEFAULT_MAVEN_URL = "https://repo1.maven.org/maven2"
TIMEOUT = 60


class FetchError(RuntimeError):
    pass


# A requests.Session, or anything with the same get(); tests pass a fake.
Session = Any


def _get(session: Session, url: str, **kwargs: Any) -> Any:
    resp = session.get(url, timeout=TIMEOUT, **kwargs)
    if resp.status_code == 404:
        raise FetchError(f"not found: {url}")
    resp.raise_for_status()
    return resp


def python_files(session: Session, pkg: PythonPackage, index_url: str) -> list[ManifestFile]:
    """Every distribution file PyPI lists for the release, with its sha256."""
    url = f"{index_url.rstrip('/')}/pypi/{pkg.package}/{pkg.version}/json"
    try:
        data = _get(session, url).json()
    except FetchError as exc:
        raise FetchError(f"{pkg.coordinate} is not on PyPI ({exc})") from exc
    files = []
    for item in data.get("urls", []):
        if item.get("yanked"):
            log.warning("%s: %s is yanked, skipping", pkg.coordinate, item["filename"])
            continue
        kind = "wheel" if item.get("packagetype") == "bdist_wheel" else "sdist"
        sha256 = item.get("digests", {}).get("sha256")
        files.append(
            ManifestFile(
                filename=item["filename"],
                entry=pkg,
                kind=kind,
                url=item["url"],
                expected={"sha256": sha256} if sha256 else {},
            )
        )
    if not files:
        raise FetchError(f"{pkg.coordinate} has no downloadable files")
    return files


def _maven_checksum(session: Session, url: str) -> dict[str, str]:
    """Prefer the published .sha256; fall back to .sha1."""
    for algorithm in ("sha256", "sha1"):
        resp = session.get(f"{url}.{algorithm}", timeout=TIMEOUT)
        if resp.status_code == 200 and resp.text.strip():
            # Some repositories write "<digest>  <filename>".
            return {algorithm: resp.text.split()[0].lower()}
    return {}


def maven_files(session: Session, art: MavenArtifact, repo_url: str) -> list[ManifestFile]:
    base = f"{repo_url.rstrip('/')}/{art.path}"
    files = []
    for ext, kind in (("jar", "jar"), ("pom", "pom")):
        filename = f"{art.artifact}-{art.version}.{ext}"
        url = f"{base}/{filename}"
        files.append(
            ManifestFile(
                filename=filename,
                entry=art,
                kind=kind,
                url=url,
                expected=_maven_checksum(session, url),
            )
        )
    return files


def download(session: Session, url: str, dest: Path) -> None:
    resp = _get(session, url, stream=True)
    tmp = dest.with_name(dest.name + ".part")
    with tmp.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            f.write(chunk)
    tmp.replace(dest)


def resolve(session: Session, entry: Entry, pypi_url: str, maven_url: str) -> list[ManifestFile]:
    if isinstance(entry, PythonPackage):
        return python_files(session, entry, pypi_url)
    return maven_files(session, entry, maven_url)


def run(
    session: Session,
    added_file: Path,
    dist: Path,
    pypi_url: str = DEFAULT_PYPI_URL,
    maven_url: str = DEFAULT_MAVEN_URL,
) -> list[ManifestFile]:
    entries = [entry_from_json(raw) for raw in json.loads(added_file.read_text())]
    dist.mkdir(parents=True, exist_ok=True)
    files: list[ManifestFile] = []
    for entry in entries:
        for mf in resolve(session, entry, pypi_url, maven_url):
            log.info("downloading %s", mf.url)
            download(session, mf.url, dist / mf.filename)
            files.append(mf)
    manifest.save(dist, files)
    log.info(
        "fetched %d file(s) for %d entr%s", len(files), len(entries), "y" if len(entries) == 1 else "ies"
    )
    return files
