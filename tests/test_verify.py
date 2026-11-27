from pathlib import Path

import pytest

from oss_allowlist import manifest, verify


def test_all_files_verify(populated_dist: Path):
    assert verify.verify(populated_dist) == []


def test_tampered_file_is_reported(populated_dist: Path):
    (populated_dist / "guava-32.1.2.jar").write_bytes(b"evil")
    [problem] = verify.verify(populated_dist)
    assert problem.startswith("guava-32.1.2.jar: sha256 mismatch")


def test_missing_file_is_reported(populated_dist: Path):
    (populated_dist / "guava-32.1.2.pom").unlink()
    assert verify.verify(populated_dist) == [f"guava-32.1.2.pom: missing from {populated_dist}"]


def test_file_without_upstream_digest_fails(populated_dist: Path):
    files = manifest.load(populated_dist)
    files[0].expected = {}
    manifest.save(populated_dist, files)
    [problem] = verify.verify(populated_dist)
    assert "no digest" in problem


def test_sha1_and_uppercase_digests(populated_dist: Path):
    files = manifest.load(populated_dist)
    path = populated_dist / files[1].filename
    files[1].expected = {"sha1": manifest.file_digest(path, "sha1").upper()}
    manifest.save(populated_dist, files)
    assert verify.verify(populated_dist) == []


def test_requires_manifest(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="oss-allowlist fetch"):
        verify.verify(tmp_path)
