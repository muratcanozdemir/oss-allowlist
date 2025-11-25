import json, subprocess

files = ["data/python.yaml", "data/maven.yaml"]
cmd = ["git", "diff", "--unified=0", "origin/main...HEAD", "--"] + files
raw = subprocess.check_output(cmd, text=True)
added = []

for line in raw.splitlines():
    if line.startswith("+") and not line.startswith("+++"):
        stripped = line[1:].strip()
        if stripped:
            if ":" in stripped:
                parts = stripped.split(":")
                if len(parts) == 2:  # PyPI
                    pkg, ver = parts
                    added.append({"type": "python", "package": pkg.strip(), "version": ver.strip()})
                elif len(parts) == 3:  # Maven
                    group, artifact, ver = parts
                    added.append({"type": "maven", "group": group.strip(), "artifact": artifact.strip(), "version": ver.strip()})

json.dump(added, open("added.json","w"))
