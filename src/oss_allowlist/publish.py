"""Publish verified artifacts to JFrog Artifactory and, optionally, an S3 cache."""

from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import manifest
from .manifest import ManifestFile
from .models import MavenArtifact, PythonPackage

log = logging.getLogger(__name__)

TIMEOUT = 300


class PublishError(RuntimeError):
    pass


@dataclass
class Config:
    pypi_url: str | None
    maven_url: str | None
    username: str | None
    password: str | None
    s3_bucket: str | None
    s3_prefix: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> Config:
        return cls(
            pypi_url=env.get("JFROG_PYPI_URL") or None,
            maven_url=env.get("JFROG_MAVEN_URL") or None,
            username=env.get("JFROG_USERNAME") or None,
            password=env.get("JFROG_API_KEY") or None,
            s3_bucket=env.get("S3_BUCKET") or None,
            s3_prefix=env.get("S3_PREFIX", "").strip("/"),
        )

    def check(self, files: list[ManifestFile]) -> None:
        missing = []
        if any(isinstance(f.entry, PythonPackage) for f in files) and not self.pypi_url:
            missing.append("JFROG_PYPI_URL")
        if any(isinstance(f.entry, MavenArtifact) for f in files) and not self.maven_url:
            missing.append("JFROG_MAVEN_URL")
        if files and not (self.username and self.password):
            missing += ["JFROG_USERNAME", "JFROG_API_KEY"]
        if missing:
            raise PublishError(f"missing configuration: {', '.join(missing)}")


def s3_key(mf: ManifestFile, filename: str, prefix: str = "") -> str:
    if isinstance(mf.entry, MavenArtifact):
        middle = f"maven/{mf.entry.path}"
    else:
        middle = f"python/{mf.entry.package}/{mf.entry.version}"
    return "/".join(p for p in (prefix, middle, filename) if p)


def publish(
    dist: Path,
    config: Config,
    *,
    session: Any = None,
    s3: Any = None,
    runner: Callable[..., Any] = subprocess.run,
    dry_run: bool = False,
) -> list[str]:
    """Upload everything in the manifest. Returns a log of the actions taken (or planned)."""
    files = manifest.load(dist)
    config.check(files)
    actions: list[str] = []

    wheels = [f for f in files if isinstance(f.entry, PythonPackage)]
    if wheels:
        cmd = ["twine", "upload", "--non-interactive", "--repository-url", str(config.pypi_url)]
        cmd += [str(dist / f.filename) for f in wheels]
        actions.append(f"twine upload {len(wheels)} file(s) to {config.pypi_url}")
        if not dry_run:
            # Credentials go through the environment so they never appear in argv.
            env = {
                **os.environ,
                "TWINE_USERNAME": str(config.username),
                "TWINE_PASSWORD": str(config.password),
            }
            runner(cmd, check=True, env=env)

    for mf in files:
        if not isinstance(mf.entry, MavenArtifact):
            continue
        url = f"{str(config.maven_url).rstrip('/')}/{mf.entry.path}/{mf.filename}"
        actions.append(f"PUT {url}")
        if dry_run:
            continue
        path = dist / mf.filename
        headers = {
            "X-Checksum-Sha1": manifest.file_digest(path, "sha1"),
            "X-Checksum-Sha256": manifest.file_digest(path, "sha256"),
        }
        with path.open("rb") as body:
            resp = session.put(
                url, data=body, headers=headers, auth=(config.username, config.password), timeout=TIMEOUT
            )
        if resp.status_code >= 300:
            raise PublishError(f"PUT {url} failed: {resp.status_code} {resp.text[:200]}")

    if config.s3_bucket:
        for mf in files:
            uploads = [(dist / mf.filename, mf.filename)]
            for report in (manifest.sbom_path(dist, mf.filename), manifest.vuln_path(dist, mf.filename)):
                if report.exists():
                    uploads.append((report, report.name))
            for path, name in uploads:
                key = s3_key(mf, name, config.s3_prefix)
                actions.append(f"s3://{config.s3_bucket}/{key}")
                if not dry_run:
                    s3.upload_file(str(path), config.s3_bucket, key)

    for a in actions:
        log.info("%s%s", "[dry run] " if dry_run else "", a)
    return actions
