import pathlib, subprocess, os

dist = pathlib.Path("dist")
jfrog_repo_url = os.environ.get("JFROG_REPO_URL")
jfrog_user = os.environ.get("JFROG_USER")
jfrog_pass = os.environ.get("JFROG_PASS")
s3_bucket = os.environ.get("S3_BUCKET")

for artifact in dist.iterdir():
    if artifact.suffix in [".whl", ".tar.gz"]:
        # Publish to JFrog PyPI
        subprocess.check_call([
            "twine", "upload", "--repository-url", jfrog_repo_url,
            "-u", jfrog_user, "-p", jfrog_pass, str(artifact)
        ])
    elif artifact.suffix == ".jar":
        # Maven deploy
        subprocess.check_call([
            "mvn", "deploy:deploy-file",
            f"-Durl={jfrog_repo_url}",
            f"-DrepositoryId=oss",
            f"-Dfile={artifact}",
            f"-DgroupId={artifact.stem.split('-')[0]}",
            f"-DartifactId={artifact.stem.split('-')[0]}",
            f"-Dversion={artifact.stem.split('-')[1]}",
            "-Dpackaging=jar"
        ])

    # Optional S3 cache
    if s3_bucket:
        subprocess.check_call(["aws", "s3", "cp", str(artifact), f"s3://{s3_bucket}/{artifact.name}"])
