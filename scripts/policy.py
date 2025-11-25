import json, pathlib, sys

dist = pathlib.Path("dist")
for vuln_file in dist.glob("*.vuln.json"):
    data = json.load(open(vuln_file))
    for match in data.get("matches", []):
        sev = match["vulnerability"]["cvss"]["nvd"].get("baseScore")
        if sev is not None and sev >= 9.0:
            print(f"Blocked {vuln_file}: critical CVE {match['vulnerability']['id']}")
            sys.exit(1)
