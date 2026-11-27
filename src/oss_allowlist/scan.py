"""SBOM generation (Syft) and vulnerability scanning (Grype)."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from . import manifest

log = logging.getLogger(__name__)

Runner = Callable[..., Any]


def sbom(dist: Path, runner: Runner = subprocess.run) -> list[Path]:
    out = []
    for mf in manifest.load(dist):
        if not mf.scannable:
            continue
        target = manifest.sbom_path(dist, mf.filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        cmd: Sequence[str] = ["syft", "scan", f"file:{dist / mf.filename}", "-q", "-o", f"syft-json={target}"]
        log.info("sbom %s", mf.filename)
        runner(cmd, check=True)
        out.append(target)
    return out


def vuln(dist: Path, runner: Runner = subprocess.run) -> list[Path]:
    out = []
    for mf in manifest.load(dist):
        if not mf.scannable:
            continue
        source = manifest.sbom_path(dist, mf.filename)
        if not source.exists():
            raise FileNotFoundError(f"{source} not found: run 'oss-allowlist sbom' first")
        target = manifest.vuln_path(dist, mf.filename)
        cmd = ["grype", f"sbom:{source}", "-q", "-o", "json", "--file", str(target)]
        log.info("scan %s", mf.filename)
        runner(cmd, check=True)
        out.append(target)
    return out
