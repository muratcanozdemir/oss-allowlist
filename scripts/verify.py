import hashlib, pathlib, sys

dist = pathlib.Path("dist")

for artifact in dist.iterdir():
    if artifact.suffix in [".whl", ".tar.gz", ".jar"]:
        h = hashlib.sha256()
        with artifact.open("rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        digest = h.hexdigest()
        print(f"SHA256({artifact.name}) = {digest}")
