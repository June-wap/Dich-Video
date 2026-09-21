"""Verify every approved CP8.6 staged model artifact against its manifest."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> int:
    root = Path(os.environ["CP86_MODEL_ROOT"])
    manifest = json.loads((root / "model-manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest["artifacts"]
    failures: list[str] = []
    for artifact in artifacts:
        relative = artifact["relative_path"]
        candidate = root / relative
        if not candidate.is_file():
            failures.append(f"missing:{relative}")
        elif candidate.stat().st_size != artifact["size_bytes"]:
            failures.append(f"size:{relative}")
        elif digest(candidate) != artifact["sha256"].lower():
            failures.append(f"sha256:{relative}")
    print(f"APPROVED_MODEL_ARTIFACTS={len(artifacts)}")
    print(f"MODEL_HASH_FAILURES={len(failures)}")
    for failure in failures:
        print(f"FAILURE={failure}")
    if not failures:
        print("CP86_MODEL_HASH_GATE=PASS")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
