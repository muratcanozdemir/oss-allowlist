import sys, pathlib, subprocess

typ = sys.argv[1]
dist = pathlib.Path("dist")
dist.mkdir(exist_ok=True)

if typ == "python":
    pkg, ver = sys.argv[2], sys.argv[3]
    subprocess.check_call(["pip", "download", f"{pkg}=={ver}", "-d", str(dist)])
elif typ == "maven":
    group, artifact, ver = sys.argv[2], sys.argv[3], sys.argv[4]
    jar_name = f"{artifact}-{ver}.jar"
    urls = [
        f"https://repo1.maven.org/maven2/{group.replace('.','/')}/{artifact}/{ver}/{jar_name}",
        f"https://your.remote.maven.repo/{group.replace('.','/')}/{artifact}/{ver}/{jar_name}"
    ]
    for url in urls:
        try:
            subprocess.check_call(["curl", "-fSL", url, "-o", str(dist/jar_name)])
            break
        except subprocess.CalledProcessError:
            continue
    else:
        raise RuntimeError(f"Failed to fetch {artifact}:{ver}")
