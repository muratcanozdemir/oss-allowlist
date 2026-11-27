import json
from pathlib import Path

import pytest

from oss_allowlist import cli, manifest


def test_help_lists_every_step(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    out = capsys.readouterr().out
    for step in ("extract", "fetch", "verify", "sbom", "vuln", "policy", "publish"):
        assert step in out


def test_verify_exit_codes(populated_dist: Path):
    assert cli.main(["verify", "--dist", str(populated_dist)]) == 0
    (populated_dist / "guava-32.1.2.jar").write_bytes(b"evil")
    assert cli.main(["verify", "--dist", str(populated_dist)]) == 1


def test_policy_exit_codes(populated_dist: Path):
    critical = {"matches": [{"vulnerability": {"id": "CVE-9", "severity": "Critical"}}]}
    for name in ("requests-2.31.0-py3-none-any.whl", "guava-32.1.2.jar"):
        path = manifest.vuln_path(populated_dist, name)
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(critical if name.endswith(".jar") else {}))
    args = ["policy", "--dist", str(populated_dist)]
    assert cli.main(args) == 1
    assert cli.main([*args, "--ignore", "CVE-9"]) == 0


def test_errors_become_exit_code_one(tmp_path: Path, caplog):
    assert cli.main(["verify", "--dist", str(tmp_path)]) == 1
    assert "FileNotFoundError" in caplog.text


def test_verbose_reraises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        cli.main(["-v", "verify", "--dist", str(tmp_path)])


def test_publish_dry_run(populated_dist: Path, monkeypatch, caplog):
    monkeypatch.setenv("JFROG_PYPI_URL", "https://p.test")
    monkeypatch.setenv("JFROG_MAVEN_URL", "https://m.test")
    monkeypatch.setenv("JFROG_USERNAME", "u")
    monkeypatch.setenv("JFROG_API_KEY", "k")
    monkeypatch.delenv("S3_BUCKET", raising=False)
    assert cli.main(["publish", "--dry-run", "--dist", str(populated_dist)]) == 0
    assert "[dry run] PUT https://m.test/com/google/guava/guava/32.1.2/guava-32.1.2.jar" in caplog.text


def test_extract_writes_github_output(monkeypatch, tmp_path: Path):
    out_file = tmp_path / "gh_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))
    monkeypatch.setattr(cli.extract, "run", lambda repo, base, output: 3)
    assert cli.main(["extract", "-o", str(tmp_path / "a.json")]) == 0
    assert out_file.read_text() == "count=3\n"
