"""Create a Decky ZIP and matching source archive from explicit allowlists."""

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package():
    version = json.loads((ROOT / "package.json").read_text("utf-8"))["version"]
    if not (ROOT / "dist/index.js").is_file():
        raise SystemExit("Run pnpm build before packaging")
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    archive = output / f"decky-live-caption-{version}.zip"
    paths = [
        ROOT / name
        for name in (
            "main.py",
            "plugin.json",
            "package.json",
            "LICENSE",
            "THIRD_PARTY_NOTICES.md",
            "README.md",
        )
    ]
    for folder in ("dist", "caption", "runtime", "scripts", "licenses", "docs"):
        paths.extend(
            p
            for p in (ROOT / folder).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        )
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as target:
        for path in sorted(paths):
            target.write(path, "decky-live-caption/" + path.relative_to(ROOT).as_posix())
    # GPL source archive uses tracked files only. Models, user settings, and credentials stay out.
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    if not any(path.startswith("src/") for path in tracked):
        raise SystemExit("Stage project sources in Git before packaging")
    source = output / f"decky-live-caption-{version}-source.zip"
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as target:
        for name in sorted(filter(None, tracked)):
            target.write(ROOT / name, "decky-live-caption/" + name)
    for path in (archive, source):
        print(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")


if __name__ == "__main__":
    package()
