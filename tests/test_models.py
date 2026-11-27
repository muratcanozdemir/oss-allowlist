from pathlib import Path

import pytest

from oss_allowlist.models import (
    CatalogError,
    MavenArtifact,
    PythonPackage,
    entry_from_json,
    entry_to_dict,
    parse_catalog,
)

REPO = Path(__file__).resolve().parents[1]


def test_parse_python_catalog():
    text = "packages:\n  - package: requests\n    version: '2.31.0'\n"
    assert parse_catalog(text, "python") == [PythonPackage("requests", "2.31.0")]


def test_parse_maven_catalog():
    text = "packages:\n  - group: g.h\n    artifact: a\n    version: 1.2.3\n"
    [art] = parse_catalog(text, "maven")
    assert art == MavenArtifact("g.h", "a", "1.2.3")
    assert art.path == "g/h/a/1.2.3"
    assert art.coordinate == "g.h:a:1.2.3"


@pytest.mark.parametrize("text", ["", "   \n", "packages:\n", "packages: []\n"])
def test_empty_catalogs(text):
    assert parse_catalog(text, "python") == []


def test_unquoted_float_version_is_rejected():
    # YAML would silently turn 1.10 into 1.1
    with pytest.raises(CatalogError, match="quote versions"):
        parse_catalog("packages:\n  - package: x\n    version: 1.10\n", "python")


@pytest.mark.parametrize(
    "text, message",
    [
        ("packages:\n  - package: x\n", "missing version"),
        ("packages:\n  - package: x\n    version: '1'\n    sha: y\n", "unknown keys sha"),
        ("packages:\n  - just-a-string\n", "must be a mapping"),
        ("- a\n- b\n", "'packages' list"),
        ("packages: [", "invalid YAML"),
        ("packages:\n  - {package: x, version: '1'}\n  - {package: x, version: '1'}\n", "duplicate"),
    ],
)
def test_malformed_catalogs(text, message):
    with pytest.raises(CatalogError, match=message):
        parse_catalog(text, "python")


def test_unknown_ecosystem():
    with pytest.raises(CatalogError, match="unknown ecosystem"):
        parse_catalog("packages:\n  - {package: x, version: '1'}\n", "npm")


@pytest.mark.parametrize("entry", [PythonPackage("a", "1"), MavenArtifact("g", "a", "1")])
def test_json_round_trip(entry):
    assert entry_from_json(entry_to_dict(entry)) == entry


@pytest.mark.parametrize("name, ecosystem", [("python.yaml", "python"), ("maven.yaml", "maven")])
def test_repository_catalogs_are_valid(name, ecosystem):
    assert parse_catalog((REPO / "data" / name).read_text(), ecosystem)
