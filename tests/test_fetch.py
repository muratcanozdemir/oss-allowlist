import json
from pathlib import Path

import pytest
from conftest import GUAVA, REQUESTS, FakeResponse, FakeSession, sha256

from oss_allowlist import fetch, manifest
from oss_allowlist.models import entry_to_dict

PYPI = "https://pypi.test"
MAVEN = "https://maven.test/repo"
WHEEL = "requests-2.31.0-py3-none-any.whl"
SDIST = "requests-2.31.0.tar.gz"


def pypi_release(session: FakeSession, yanked_extra: bool = False) -> None:
    urls = [
        {
            "filename": WHEEL,
            "url": f"https://files.test/{WHEEL}",
            "packagetype": "bdist_wheel",
            "digests": {"sha256": sha256(b"wheel")},
        },
        {
            "filename": SDIST,
            "url": f"https://files.test/{SDIST}",
            "packagetype": "sdist",
            "digests": {"sha256": sha256(b"sdist")},
        },
    ]
    if yanked_extra:
        urls.append({"filename": "old.whl", "url": "https://files.test/old.whl", "yanked": True})
    session.routes[f"{PYPI}/pypi/requests/2.31.0/json"] = FakeResponse(payload={"urls": urls})
    session.routes[f"https://files.test/{WHEEL}"] = FakeResponse(content=b"wheel")
    session.routes[f"https://files.test/{SDIST}"] = FakeResponse(content=b"sdist")


def test_python_files_lists_all_distributions_and_skips_yanked(session):
    pypi_release(session, yanked_extra=True)
    files = fetch.python_files(session, REQUESTS, PYPI)
    assert [(f.filename, f.kind) for f in files] == [(WHEEL, "wheel"), (SDIST, "sdist")]
    assert files[0].expected == {"sha256": sha256(b"wheel")}


def test_python_release_not_found(session):
    with pytest.raises(fetch.FetchError, match="requests==2.31.0 is not on PyPI"):
        fetch.python_files(session, REQUESTS, PYPI)


def test_python_release_without_files(session):
    session.routes[f"{PYPI}/pypi/requests/2.31.0/json"] = FakeResponse(payload={"urls": []})
    with pytest.raises(fetch.FetchError, match="no downloadable files"):
        fetch.python_files(session, REQUESTS, PYPI)


def test_maven_prefers_sha256_and_falls_back_to_sha1(session):
    base = f"{MAVEN}/com/google/guava/guava/32.1.2"
    session.routes[f"{base}/guava-32.1.2.jar.sha256"] = FakeResponse(content=b"ABC123  guava-32.1.2.jar\n")
    session.routes[f"{base}/guava-32.1.2.pom.sha1"] = FakeResponse(content=b"def456\n")
    jar, pom = fetch.maven_files(session, GUAVA, MAVEN + "/")
    assert jar.url == f"{base}/guava-32.1.2.jar" and jar.kind == "jar"
    assert jar.expected == {"sha256": "abc123"}
    assert pom.expected == {"sha1": "def456"}


def test_maven_without_checksums_has_empty_expected(session):
    jar, _ = fetch.maven_files(session, GUAVA, MAVEN)
    assert jar.expected == {}


def test_run_downloads_and_writes_manifest(session, tmp_path: Path):
    pypi_release(session)
    base = f"{MAVEN}/com/google/guava/guava/32.1.2"
    for ext, body in (("jar", b"jar"), ("pom", b"pom")):
        session.routes[f"{base}/guava-32.1.2.{ext}"] = FakeResponse(content=body)
        session.routes[f"{base}/guava-32.1.2.{ext}.sha256"] = FakeResponse(content=sha256(body).encode())
    added = tmp_path / "added.json"
    added.write_text(json.dumps([entry_to_dict(REQUESTS), entry_to_dict(GUAVA)]))
    dist = tmp_path / "dist"

    files = fetch.run(session, added, dist, PYPI, MAVEN)

    assert [f.filename for f in files] == [WHEEL, SDIST, "guava-32.1.2.jar", "guava-32.1.2.pom"]
    assert (dist / "guava-32.1.2.jar").read_bytes() == b"jar"
    assert not list(dist.glob("*.part"))
    assert [f.to_json() for f in manifest.load(dist)] == [f.to_json() for f in files]


def test_run_fails_on_missing_download(session, tmp_path: Path):
    session.routes[f"{PYPI}/pypi/requests/2.31.0/json"] = FakeResponse(
        payload={"urls": [{"filename": WHEEL, "url": "https://files.test/gone", "digests": {}}]}
    )
    added = tmp_path / "added.json"
    added.write_text(json.dumps([entry_to_dict(REQUESTS)]))
    with pytest.raises(fetch.FetchError, match="not found"):
        fetch.run(session, added, tmp_path / "dist", PYPI, MAVEN)


def test_run_with_nothing_added(session, tmp_path: Path):
    added = tmp_path / "added.json"
    added.write_text("[]")
    assert fetch.run(session, added, tmp_path / "dist") == []
    assert manifest.load(tmp_path / "dist") == []
