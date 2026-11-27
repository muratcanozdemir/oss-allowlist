from pathlib import Path

import pytest

from oss_allowlist import manifest, scan


class Recorder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, cmd, check):
        assert check is True
        self.calls.append(list(cmd))


def test_sbom_runs_syft_for_scannable_files_only(populated_dist: Path):
    run = Recorder()
    out = scan.sbom(populated_dist, runner=run)
    assert [c[0] for c in run.calls] == ["syft", "syft"]  # pom is skipped
    assert run.calls[0] == [
        "syft",
        "scan",
        f"file:{populated_dist / 'requests-2.31.0-py3-none-any.whl'}",
        "-q",
        "-o",
        f"syft-json={out[0]}",
    ]
    assert out[1] == manifest.sbom_path(populated_dist, "guava-32.1.2.jar")
    assert out[0].parent.is_dir()


def test_vuln_runs_grype_on_sboms(populated_dist: Path):
    for p in scan.sbom(populated_dist, runner=Recorder()):
        p.write_text("{}")
    run = Recorder()
    out = scan.vuln(populated_dist, runner=run)
    sbom = manifest.sbom_path(populated_dist, "guava-32.1.2.jar")
    assert run.calls[1] == ["grype", f"sbom:{sbom}", "-q", "-o", "json", "--file", str(out[1])]
    # -f is grype's --fail-on, not an output file: make sure it never comes back
    assert all("-f" not in c for c in run.calls)


def test_vuln_requires_sbom(populated_dist: Path):
    with pytest.raises(FileNotFoundError, match="oss-allowlist sbom"):
        scan.vuln(populated_dist, runner=Recorder())
