import json
from pathlib import Path

import pytest

from oss_allowlist import manifest, policy


def match(vid: str, severity: str, name: str = "lib", version: str = "1.0") -> dict:
    return {
        "vulnerability": {"id": vid, "severity": severity},
        "artifact": {"name": name, "version": version},
    }


REPORT = {
    "matches": [
        match("CVE-1", "Critical"),
        match("CVE-2", "High"),
        match("CVE-3", "Low"),
        match("GHSA-x", "Unknown"),
        match("CVE-1", "Critical"),  # grype can repeat a match per location
    ]
}


@pytest.mark.parametrize(
    "fail_on, expected",
    [
        ("critical", ["CVE-1 (Critical) in lib 1.0"]),
        ("high", ["CVE-1 (Critical) in lib 1.0", "CVE-2 (High) in lib 1.0"]),
        ("negligible", ["CVE-1 (Critical) in lib 1.0", "CVE-2 (High) in lib 1.0", "CVE-3 (Low) in lib 1.0"]),
    ],
)
def test_threshold(fail_on, expected):
    assert policy.violations(REPORT, fail_on) == expected


def test_ignore_list_is_case_insensitive():
    assert policy.violations(REPORT, "high", ignore=["cve-1"]) == ["CVE-2 (High) in lib 1.0"]


def test_empty_report():
    assert policy.violations({}, "low") == []
    assert policy.violations({"matches": []}, "low") == []


def test_unknown_threshold():
    with pytest.raises(ValueError, match="unknown severity"):
        policy.violations(REPORT, "severe")


def write_reports(dist: Path, reports: dict[str, dict]) -> None:
    for name, report in reports.items():
        path = manifest.vuln_path(dist, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report))


def test_evaluate_blocks_only_offending_files(populated_dist: Path):
    write_reports(
        populated_dist,
        {"requests-2.31.0-py3-none-any.whl": {"matches": []}, "guava-32.1.2.jar": REPORT},
    )
    assert policy.evaluate(populated_dist) == {"guava-32.1.2.jar": ["CVE-1 (Critical) in lib 1.0"]}
    assert policy.evaluate(populated_dist, ignore=["CVE-1"]) == {}


def test_evaluate_blocks_files_without_report(populated_dist: Path):
    write_reports(populated_dist, {"guava-32.1.2.jar": {"matches": []}})
    blocked = policy.evaluate(populated_dist)
    assert list(blocked) == ["requests-2.31.0-py3-none-any.whl"]
    assert "no vulnerability report" in blocked["requests-2.31.0-py3-none-any.whl"][0]
