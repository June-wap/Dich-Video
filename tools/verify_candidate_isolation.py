"""Verifies strict candidate isolation across the 4 candidate trees:
- BASELINE
- candidate-a-vc-only
- candidate-b-sp021-only
- candidate-c-combined

Assertions:
1. BASELINE vs A: SentencePiece identical; only approved VC runtime files differ.
2. BASELINE vs B: VC runtime files identical; only approved SentencePiece files differ.
3. C vs A: VC runtime set identical; SentencePiece is the intended difference.
4. C vs B: SentencePiece 0.2.1 files identical; VC runtime set is the intended difference.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ISOLATION_DIR = REPO_ROOT / "release-candidates" / "cleanvm-isolation"

BASELINE = ISOLATION_DIR / "baseline"
CAND_A = ISOLATION_DIR / "candidate-a-vc-only"
CAND_B = ISOLATION_DIR / "candidate-b-sp021-only"
CAND_C = ISOLATION_DIR / "candidate-c-combined"

VC_DLLS = [
    "concrt140.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll",
    "vccorlib140.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "vcruntime140_threads.dll",
]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()

def get_sp_hashes(tree: Path) -> dict:
    sp_dir = tree / "Lib" / "site-packages" / "sentencepiece"
    dist_info = None
    for d in (tree / "Lib" / "site-packages").glob("sentencepiece-*.dist-info"):
        dist_info = d.name
        break

    pyd = sp_dir / "_sentencepiece.cp312-win_amd64.pyd"
    py = sp_dir / "__init__.py"
    return {
        "dist_info": dist_info,
        "pyd_exists": pyd.is_file(),
        "pyd_sha256": sha256(pyd) if pyd.is_file() else None,
        "pyd_size": pyd.stat().st_size if pyd.is_file() else 0,
        "init_sha256": sha256(py) if py.is_file() else None,
    }

def get_vc_hashes(tree: Path) -> dict:
    result = {}
    for name in VC_DLLS:
        dll_file = tree / name
        if dll_file.is_file():
            result[name] = {
                "exists": True,
                "size": dll_file.stat().st_size,
                "sha256": sha256(dll_file),
            }
        else:
            result[name] = {"exists": False}
    return result

def main():
    print("=================================================================")
    print("           VERIFYING CANDIDATE ISOLATION & HASHES                ")
    print("=================================================================")

    manifests = {}
    for name, path in [("BASELINE", BASELINE), ("CANDIDATE_A", CAND_A), ("CANDIDATE_B", CAND_B), ("CANDIDATE_C", CAND_C)]:
        manifests[name] = {
            "sentencepiece": get_sp_hashes(path),
            "vc_runtime": get_vc_hashes(path),
        }
        print(f"\n--- {name} ---")
        sp = manifests[name]["sentencepiece"]
        print(f"  SentencePiece dist-info: {sp['dist_info']}")
        print(f"  SentencePiece PYD SHA256: {sp['pyd_sha256']}")
        vc = manifests[name]["vc_runtime"]
        present_vc = [k for k, v in vc.items() if v["exists"]]
        print(f"  VC DLLs present ({len(present_vc)}): {', '.join(present_vc)}")

    # Assertions
    errors = []

    # 1. BASELINE vs A
    # SP identical
    if manifests["BASELINE"]["sentencepiece"] != manifests["CANDIDATE_A"]["sentencepiece"]:
        errors.append("BASELINE vs CANDIDATE_A: SentencePiece files mismatch!")
    # VC differs
    if manifests["BASELINE"]["vc_runtime"] == manifests["CANDIDATE_A"]["vc_runtime"]:
        errors.append("BASELINE vs CANDIDATE_A: VC runtime files unexpectedly identical!")

    # 2. BASELINE vs B
    # VC identical
    if manifests["BASELINE"]["vc_runtime"] != manifests["CANDIDATE_B"]["vc_runtime"]:
        errors.append("BASELINE vs CANDIDATE_B: VC runtime files mismatch!")
    # SP differs
    if manifests["BASELINE"]["sentencepiece"] == manifests["CANDIDATE_B"]["sentencepiece"]:
        errors.append("BASELINE vs CANDIDATE_B: SentencePiece files unexpectedly identical!")

    # 3. C vs A
    # VC identical
    if manifests["CANDIDATE_C"]["vc_runtime"] != manifests["CANDIDATE_A"]["vc_runtime"]:
        errors.append("CANDIDATE_C vs CANDIDATE_A: VC runtime files mismatch!")
    # SP differs
    if manifests["CANDIDATE_C"]["sentencepiece"] == manifests["CANDIDATE_A"]["sentencepiece"]:
        errors.append("CANDIDATE_C vs CANDIDATE_A: SentencePiece files unexpectedly identical!")

    # 4. C vs B
    # SP identical
    if manifests["CANDIDATE_C"]["sentencepiece"] != manifests["CANDIDATE_B"]["sentencepiece"]:
        errors.append("CANDIDATE_C vs CANDIDATE_B: SentencePiece files mismatch!")
    # VC differs
    if manifests["CANDIDATE_C"]["vc_runtime"] == manifests["CANDIDATE_B"]["vc_runtime"]:
        errors.append("CANDIDATE_C vs CANDIDATE_B: VC runtime files unexpectedly identical!")

    # Check expected hashes for 0.2.1
    EXPECTED_021_PYD = "F1069EAA45CFA5D6D81F7B46876B80860FE9147D28D84C7057ED952E84B064E5"
    for cand in ("CANDIDATE_B", "CANDIDATE_C"):
        actual = manifests[cand]["sentencepiece"]["pyd_sha256"]
        if actual != EXPECTED_021_PYD:
            errors.append(f"{cand} SentencePiece PYD hash {actual} != expected {EXPECTED_021_PYD}")

    out_file = ISOLATION_DIR / "isolation_manifest.json"
    out_file.write_text(json.dumps(manifests, indent=2), encoding="utf-8")
    print(f"\nWrote full isolation manifest to: {out_file}")

    if errors:
        print("\n[FAIL] Isolation verification FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\n[PASS] All 4 candidate isolation assertions VALIDATED 100%!")

if __name__ == "__main__":
    main()
