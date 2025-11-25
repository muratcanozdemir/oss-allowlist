import json, subprocess, sys

added = json.load(open(sys.argv[1]))

for entry in added:
    typ = entry["type"]
    if typ == "python":
        subprocess.check_call(["python", "scripts/fetch.py", "python", entry["package"], entry["version"]])
    elif typ == "maven":
        subprocess.check_call([
            "python", "scripts/fetch.py", "maven", entry["group"], entry["artifact"], entry["version"]
        ])
