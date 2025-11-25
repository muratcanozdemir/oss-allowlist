# OSS Allowlist Intake

PR-driven pipeline to ingest, verify, scan, and publish Python and Maven artifacts. Provides SBOM generation, CVE scanning, SHA256 verification, and deployment to JFrog or S3.

---

## Features

- Extract new or updated artifacts from PRs.
- Verify integrity via SHA256 checks.
- Generate SBOMs using Syft CLI.
- Scan artifacts for known vulnerabilities using Grype CLI.
- Enforce allowlist policies for approved packages only.
- Publish verified artifacts to JFrog Artifactory or S3 cache.
- Supports Python (PyPI) and Maven repositories.
- CI/CD compatible with GitHub Actions and `uv` package manager.

---

## Requirements

- Python ≥ 3.12
- `uv` package manager
- Grype CLI (v0.77.0) installed or available in PATH
- Syft CLI (v0.88.0) installed or available in PATH
- Access to JFrog Artifactory and S3 (credentials stored as environment variables or GitHub secrets)

---

## Installation

```bash
# Install Python dependencies
uv sync
```
## Usage
```bash
uv run extract-added
uv run intake
uv run verify
uv run sbom
uv run vuln
uv run policy
uv run publish
```