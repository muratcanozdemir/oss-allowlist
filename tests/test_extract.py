import json
import subprocess
from pathlib import Path

import pytest

from oss_allowlist import extract
from oss_allowlist.models import MavenArtifact, PythonPackage

BASE = "packages:\n  - package: requests\n    version: '2.31.0'\n"


def test_added_entries_detects_new_and_bumped_versions():
    head = BASE + "  - package: requests\n    version: '2.32.0'\n  - package: idna\n    version: '3.7'\n"
    assert extract.added_entries(BASE, head, "python") == [
        PythonPackage("requests", "2.32.0"),
        PythonPackage("idna", "3.7"),
    ]


def test_removals_and_reordering_are_not_additions():
    head = "packages:\n  - package: idna\n    version: '3.7'\n"
    base = BASE + "  - package: idna\n    version: '3.7'\n"
    assert extract.added_entries(base, head, "python") == []


def test_new_catalog_file_counts_everything():
    assert extract.added_entries("", BASE, "python") == [PythonPackage("requests", "2.31.0")]


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@example.test")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "data").mkdir()
    (tmp_path / "data/python.yaml").write_text(BASE)
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    git(tmp_path, "switch", "-qc", "feature")
    return tmp_path


def test_run_against_git_history(repo: Path, tmp_path: Path):
    # maven.yaml is new on the branch; python.yaml gains one entry.
    (repo / "data/python.yaml").write_text(BASE + "  - package: idna\n    version: '3.7'\n")
    (repo / "data/maven.yaml").write_text("packages:\n  - {group: g, artifact: a, version: '1.0'}\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "add")
    # main moves on after the branch point: its changes must not leak into the diff.
    git(repo, "switch", "-q", "main")
    (repo / "data/python.yaml").write_text(BASE + "  - package: six\n    version: '1.16.0'\n")
    git(repo, "commit", "-qam", "main moved")
    git(repo, "switch", "-q", "feature")

    out = tmp_path / "added.json"
    assert extract.run(repo, "main", out) == 2
    assert json.loads(out.read_text()) == [
        {"type": "python", "package": "idna", "version": "3.7"},
        {"type": "maven", "group": "g", "artifact": "a", "version": "1.0"},
    ]
    assert extract.extract(repo, "main")[1] == MavenArtifact("g", "a", "1.0")


def test_no_changes(repo: Path, tmp_path: Path):
    assert extract.run(repo, "main", tmp_path / "added.json") == 0


def test_bad_ref_raises(repo: Path):
    with pytest.raises(subprocess.CalledProcessError):
        extract.extract(repo, "does-not-exist")
