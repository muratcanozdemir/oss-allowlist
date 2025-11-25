import pathlib, subprocess

dist = pathlib.Path("dist")
for artifact in dist.iterdir():
    if artifact.suffix in [".whl", ".tar.gz", ".jar"]:
        sbom_file = artifact.with_suffix(".sbom.json")
        subprocess.check_call(["syft", str(artifact), "-o", "json", "-q", "-f", str(sbom_file)])
