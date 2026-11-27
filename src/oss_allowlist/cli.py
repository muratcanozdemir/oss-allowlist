"""Command line: ``oss-allowlist <step>``."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import requests

from . import extract, fetch, policy, publish, scan, verify

log = logging.getLogger("oss_allowlist")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "oss-allowlist"
    return s


def cmd_extract(args: argparse.Namespace) -> int:
    count = extract.run(Path(args.repo), args.base, Path(args.output))
    if gh_out := os.environ.get("GITHUB_OUTPUT"):
        with open(gh_out, "a") as f:
            f.write(f"count={count}\n")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    fetch.run(_session(), Path(args.added), args.dist, args.pypi_url, args.maven_url)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    problems = verify.verify(args.dist)
    for p in problems:
        log.error(p)
    return 1 if problems else 0


def cmd_sbom(args: argparse.Namespace) -> int:
    scan.sbom(args.dist)
    return 0


def cmd_vuln(args: argparse.Namespace) -> int:
    scan.vuln(args.dist)
    return 0


def cmd_policy(args: argparse.Namespace) -> int:
    blocked = policy.evaluate(args.dist, args.fail_on, args.ignore)
    for filename, problems in blocked.items():
        for p in problems:
            log.error("blocked %s: %s", filename, p)
    if not blocked:
        log.info("policy passed (fail-on %s)", args.fail_on)
    return 1 if blocked else 0


def cmd_publish(args: argparse.Namespace) -> int:
    config = publish.Config.from_env()
    s3 = None
    if config.s3_bucket and not args.dry_run:
        import boto3

        s3 = boto3.client("s3")
    publish.publish(args.dist, config, session=_session(), s3=s3, dry_run=args.dry_run)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="oss-allowlist", description=__doc__)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    def add(name: str, func, help: str) -> argparse.ArgumentParser:  # type: ignore[no-untyped-def]
        sp = sub.add_parser(name, help=help)
        sp.set_defaults(func=func)
        if name != "extract":
            sp.add_argument(
                "--dist", type=Path, default=Path("dist"), help="working directory (default: dist)"
            )
        return sp

    sp = add("extract", cmd_extract, "list catalog entries added since a base ref")
    sp.add_argument("--base", default="origin/main", help="git ref to diff against (default: origin/main)")
    sp.add_argument("--repo", default=".", help="repository root (default: .)")
    sp.add_argument("-o", "--output", default="added.json")

    sp = add("fetch", cmd_fetch, "download added artifacts and their upstream digests")
    sp.add_argument("added", nargs="?", default="added.json")
    sp.add_argument("--pypi-url", default=os.environ.get("PYPI_URL", fetch.DEFAULT_PYPI_URL))
    sp.add_argument("--maven-url", default=os.environ.get("MAVEN_REMOTE_URL", fetch.DEFAULT_MAVEN_URL))

    add("verify", cmd_verify, "check downloaded files against upstream digests")
    add("sbom", cmd_sbom, "generate SBOMs with syft")
    add("vuln", cmd_vuln, "scan SBOMs with grype")

    sp = add("policy", cmd_policy, "fail if any finding is at or above a severity")
    sp.add_argument(
        "--fail-on",
        default=os.environ.get("POLICY_FAIL_ON", "critical"),
        choices=policy.SEVERITIES,
    )
    sp.add_argument(
        "--ignore", action="append", default=[], metavar="VULN_ID", help="accepted vulnerability id"
    )

    sp = add("publish", cmd_publish, "upload to JFrog (and S3 if S3_BUCKET is set)")
    sp.add_argument("--dry-run", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(format="%(levelname)s %(message)s")
    log.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    try:
        return int(args.func(args))
    except Exception as exc:  # surface a one-line error instead of a traceback in CI logs
        if args.verbose:
            raise
        log.error("%s: %s", type(exc).__name__, exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
