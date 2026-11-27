from pathlib import Path

import pytest
from conftest import GUAVA, REQUESTS, FakeSession

from oss_allowlist import manifest, publish
from oss_allowlist.manifest import ManifestFile

CONFIG = publish.Config(
    pypi_url="https://jfrog.test/api/pypi/pypi-local",
    maven_url="https://jfrog.test/maven-local/",
    username="bot",
    password="s3cret",
    s3_bucket=None,
)


class FakeS3:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, str]] = []

    def upload_file(self, path: str, bucket: str, key: str) -> None:
        self.uploads.append((Path(path).name, bucket, key))


class Recorder:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, cmd, check, env):
        self.calls.append({"cmd": cmd, "env": env})


def test_config_from_env():
    cfg = publish.Config.from_env(
        {
            "JFROG_PYPI_URL": "p",
            "JFROG_MAVEN_URL": "m",
            "JFROG_USERNAME": "u",
            "JFROG_API_KEY": "k",
            "S3_BUCKET": "",
            "S3_PREFIX": "/cache/",
        }
    )
    assert cfg == publish.Config("p", "m", "u", "k", None, "cache")


def test_config_reports_everything_missing(populated_dist: Path):
    with pytest.raises(publish.PublishError) as exc:
        publish.publish(populated_dist, publish.Config(None, None, None, None, None))
    assert str(exc.value) == (
        "missing configuration: JFROG_PYPI_URL, JFROG_MAVEN_URL, JFROG_USERNAME, JFROG_API_KEY"
    )


def test_config_only_requires_what_is_used():
    publish.Config(None, "m", "u", "k", None).check([ManifestFile("a.jar", GUAVA, "jar", "u")])
    publish.Config("p", None, "u", "k", None).check([ManifestFile("a.whl", REQUESTS, "wheel", "u")])


def test_publish(populated_dist: Path):
    session, run = FakeSession(), Recorder()
    publish.publish(populated_dist, CONFIG, session=session, runner=run)

    [twine] = run.calls
    assert twine["cmd"][:5] == ["twine", "upload", "--non-interactive", "--repository-url", CONFIG.pypi_url]
    assert twine["cmd"][5:] == [str(populated_dist / "requests-2.31.0-py3-none-any.whl")]
    assert "s3cret" not in " ".join(twine["cmd"])
    assert twine["env"]["TWINE_PASSWORD"] == "s3cret"

    assert [p["url"] for p in session.puts] == [
        "https://jfrog.test/maven-local/com/google/guava/guava/32.1.2/guava-32.1.2.jar",
        "https://jfrog.test/maven-local/com/google/guava/guava/32.1.2/guava-32.1.2.pom",
    ]
    jar = session.puts[0]
    assert jar["body"] == b"jar-bytes"
    assert jar["auth"] == ("bot", "s3cret")
    assert jar["headers"]["X-Checksum-Sha256"] == manifest.file_digest(
        populated_dist / "guava-32.1.2.jar", "sha256"
    )


def test_publish_fails_on_rejected_put(populated_dist: Path):
    session = FakeSession(put_status=403)
    with pytest.raises(publish.PublishError, match="403"):
        publish.publish(populated_dist, CONFIG, session=session, runner=Recorder())


def test_publish_to_s3_includes_reports(populated_dist: Path):
    sbom = manifest.sbom_path(populated_dist, "guava-32.1.2.jar")
    sbom.parent.mkdir()
    sbom.write_text("{}")
    s3 = FakeS3()
    cfg = publish.Config(**{**CONFIG.__dict__, "s3_bucket": "cache", "s3_prefix": "oss"})
    publish.publish(populated_dist, cfg, session=FakeSession(), s3=s3, runner=Recorder())
    assert s3.uploads == [
        (
            "requests-2.31.0-py3-none-any.whl",
            "cache",
            "oss/python/requests/2.31.0/requests-2.31.0-py3-none-any.whl",
        ),
        ("guava-32.1.2.jar", "cache", "oss/maven/com/google/guava/guava/32.1.2/guava-32.1.2.jar"),
        (
            "guava-32.1.2.jar.sbom.json",
            "cache",
            "oss/maven/com/google/guava/guava/32.1.2/guava-32.1.2.jar.sbom.json",
        ),
        ("guava-32.1.2.pom", "cache", "oss/maven/com/google/guava/guava/32.1.2/guava-32.1.2.pom"),
    ]


def test_dry_run_touches_nothing(populated_dist: Path):
    session, run = FakeSession(), Recorder()
    cfg = publish.Config(**{**CONFIG.__dict__, "s3_bucket": "cache"})
    actions = publish.publish(populated_dist, cfg, session=session, s3=None, runner=run, dry_run=True)
    assert run.calls == [] and session.puts == []
    assert len(actions) == 1 + 2 + 3  # twine, two PUTs, three S3 objects
