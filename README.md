# OSS Allowlist Intake

PR-driven pipeline that admits Python and Maven artifacts to an internal mirror. Adding a package to
`data/*.yaml` in a pull request downloads it, verifies it against upstream digests, generates an SBOM,
scans it for known vulnerabilities and enforces a severity policy. Merging the PR publishes it to JFrog
Artifactory (and optionally an S3 cache).

## Adding a package

Edit the catalog and open a PR. Quote versions: YAML reads an unquoted `1.10` as the number `1.1`, so
non-string versions are rejected.

```yaml
# data/python.yaml
packages:
  - package: requests
    version: "2.31.0"
```

```yaml
# data/maven.yaml
packages:
  - group: com.google.guava
    artifact: guava
    version: "32.1.2"
```

Only entries that are new relative to the PR's merge base are processed. A version bump is a new entry.

## Pipeline

| Step | Command | What it does |
|------|---------|--------------|
| extract | `oss-allowlist extract --base origin/main` | Diffs the catalogs against the merge base, writes `added.json` |
| fetch | `oss-allowlist fetch added.json` | Python: every non-yanked file of the release from the PyPI JSON API, with its sha256. Maven: the jar and pom, with the published `.sha256` (or `.sha1`). Writes `dist/` and `dist/manifest.json` |
| verify | `oss-allowlist verify` | Fails if any file doesn't match its upstream digest, or upstream published none |
| sbom | `oss-allowlist sbom` | Syft SBOM per artifact → `dist/reports/<file>.sbom.json` |
| vuln | `oss-allowlist vuln` | Grype scan of each SBOM → `dist/reports/<file>.vuln.json` |
| policy | `oss-allowlist policy [--fail-on high] [--ignore CVE-…]` | Fails on any finding at or above the threshold (default `critical`, or `POLICY_FAIL_ON`), or on a missing report |
| publish | `oss-allowlist publish [--dry-run]` | twine upload for Python, HTTP PUT with checksum headers for Maven, plus S3 copies of artifacts and reports |

Every step exits non-zero on failure; add `-v` for a traceback.

## Configuration

| Variable | Used by | Notes |
|----------|---------|-------|
| `PYPI_URL` | fetch | Default `https://pypi.org` |
| `MAVEN_REMOTE_URL` | fetch | Default `https://repo1.maven.org/maven2` |
| `POLICY_FAIL_ON` | policy | `negligible`, `low`, `medium`, `high`, `critical` |
| `JFROG_PYPI_URL` | publish | Artifactory PyPI repo, e.g. `https://acme.jfrog.io/artifactory/api/pypi/pypi-local` |
| `JFROG_MAVEN_URL` | publish | Artifactory Maven repo, e.g. `https://acme.jfrog.io/artifactory/maven-local` |
| `JFROG_USERNAME`, `JFROG_API_KEY` | publish | Passed to twine via environment, never on the command line |
| `S3_BUCKET`, `S3_PREFIX` | publish | Optional cache; keys are `<prefix>/python/<pkg>/<ver>/…` and `<prefix>/maven/<group path>/<artifact>/<ver>/…` |

In GitHub, set the URLs and `S3_BUCKET` as repository **variables** and the credentials (`JFROG_*`,
`AWS_*`) as **secrets**.

## Workflows

- `ci.yaml`: lint (ruff), types (mypy, strict) and tests on every push and PR.
- `intake.yaml`: on PRs touching `data/*.yaml`, runs extract → policy and uploads the reports as a build
  artifact; on push to `main` it repeats the checks and publishes. Runs on a self-hosted runner with Syft
  and Grype pinned in the workflow.

## Development

Requires Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/). Syft and Grype are only needed to run the
`sbom` and `vuln` steps for real; the tests don't call them or the network.

```bash
uv sync
uv run pytest
uv run ruff check src tests && uv run ruff format --check src tests
uv run mypy
```
