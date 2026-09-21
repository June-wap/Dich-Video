"""Read-only integrity audit for CP8.2 staged runtime manifests."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main(root: Path, output: Path) -> None:
    result: dict[str, object] = {"runtimes": {}}
    for name in ("runtime-main", "runtime-chatterbox"):
        runtime = root / ".runtime" / "cp82" / name
        manifest = root / ".runtime" / "cp82" / f"{name}-manifest.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        mismatches: list[str] = []
        for entry in data["files"]:
            candidate = runtime / entry["relative_path"]
            if (not candidate.is_file() or candidate.stat().st_size != entry["size_bytes"]
                    or digest(candidate) != entry["sha256"]):
                mismatches.append(entry["relative_path"])
        result["runtimes"][name] = {
            "file_count": len(data["files"]),
            "mismatch_count": len(mismatches),
            "mismatch_sample": mismatches[:10],
            "metadata": {key: data.get(key) for key in (
                "python_version", "python_architecture", "torch_version",
                "torchaudio_version", "torchao_version", "cuda_build",
            )},
        }
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
