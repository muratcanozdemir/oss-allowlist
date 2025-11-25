import pathlib, subprocess

dist = pathlib.Path("dist")
for sbom in dist.glob("*.sbom.json"):
    vuln_file = sbom.with_name(sbom.stem + ".vuln.json")
    subprocess.check_call(["grype", str(sbom), "-o", "json", "-q", "-f", str(vuln_file)])
