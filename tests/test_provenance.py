import hashlib
import json
from pathlib import Path


def test_vendored_ocr_sources_match_pinned_upstream():
    root = Path(__file__).resolve().parents[1]
    lock = json.loads((root / "upstream-lock.json").read_text("utf-8"))
    for name, digest in lock["decky-translator"]["files"].items():
        # Compare normalized source bytes because Git uses LF on every platform.
        content = (root / name).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(content).hexdigest() == digest
