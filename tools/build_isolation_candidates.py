"""Builds four independent portable runtime trees in release-candidates\\cleanvm-isolation.

Trees:
1. baseline: SP 0.2.2 + baseline VC runtime DLLs
2. candidate-a-vc-only: SP 0.2.2 + new VC runtime DLLs (10 DLLs)
3. candidate-b-sp021-only: SP 0.2.1 + baseline VC runtime DLLs
4. candidate-c-combined: SP 0.2.1 + new VC runtime DLLs (10 DLLs)

Safety guarantee:
- Replaced files (VC DLLs and SentencePiece directories) are COPIED, never hardlinked.
- Untouched files are hardlinked to conserve disk space (0 MB extra for 8 GB runtime).
"""
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_SRC = REPO_ROOT / "release-candidates" / "runtime-main-baseline"
DEST_ROOT = REPO_ROOT / "release-candidates" / "cleanvm-isolation"

PAYLOAD_VC = REPO_ROOT / "release" / "vm-isolation-test" / "candidate_a_vc_only"
PAYLOAD_SP021 = REPO_ROOT / "release" / "vm-isolation-test" / "candidate_b_sp_only" / "site-packages"

VC_DLL_NAMES = {
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
}

def create_tree(dest_dir: Path, vc_mode: str, sp_mode: str):
    print(f"\n[+] Building {dest_dir.name} (VC={vc_mode}, SP={sp_mode})...", flush=True)
    if dest_dir.exists():
        print(f"    Cleaning existing {dest_dir.name}...", flush=True)
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 1. Hardlink base runtime, skipping VC DLLs in root and sentencepiece in site-packages
    for root, dirs, files in os.walk(BASELINE_SRC):
        rel_path = Path(root).relative_to(BASELINE_SRC)
        target_root = dest_dir / rel_path

        # Prune sentencepiece directories so os.walk does not traverse into them
        if rel_path.name.lower() == "site-packages":
            dirs[:] = [d for d in dirs if not d.lower().startswith("sentencepiece")]

        target_root.mkdir(parents=True, exist_ok=True)

        for f in files:
            # Skip root VC DLLs
            if rel_path == Path(".") and f.lower() in VC_DLL_NAMES:
                continue

            src_file = Path(root) / f
            dst_file = target_root / f

            try:
                os.link(src_file, dst_file)
            except Exception:
                shutil.copy2(src_file, dst_file)

    # 2. Apply VC Runtime DLLs (always fresh COPIES, never hardlinks)
    if vc_mode == "baseline":
        for name in ("vcruntime140.dll", "vcruntime140_1.dll"):
            src = BASELINE_SRC / name
            if src.exists():
                shutil.copy2(src, dest_dir / name)
    elif vc_mode == "new":
        for dll_file in sorted(PAYLOAD_VC.glob("*.dll")):
            shutil.copy2(dll_file, dest_dir / dll_file.name)
    else:
        raise ValueError(f"Unknown vc_mode: {vc_mode}")

    # 3. Apply SentencePiece (always fresh COPIES, never hardlinks)
    site_packages = dest_dir / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)

    if sp_mode == "0.2.2":
        shutil.copytree(BASELINE_SRC / "Lib" / "site-packages" / "sentencepiece", site_packages / "sentencepiece")
        shutil.copytree(BASELINE_SRC / "Lib" / "site-packages" / "sentencepiece-0.2.2.dist-info", site_packages / "sentencepiece-0.2.2.dist-info")
    elif sp_mode == "0.2.1":
        shutil.copytree(PAYLOAD_SP021 / "sentencepiece", site_packages / "sentencepiece")
        shutil.copytree(PAYLOAD_SP021 / "sentencepiece-0.2.1.dist-info", site_packages / "sentencepiece-0.2.1.dist-info")
    else:
        raise ValueError(f"Unknown sp_mode: {sp_mode}")

    print(f"    [OK] {dest_dir.name} successfully created.", flush=True)

def main():
    DEST_ROOT.mkdir(parents=True, exist_ok=True)
    create_tree(DEST_ROOT / "baseline", vc_mode="baseline", sp_mode="0.2.2")
    create_tree(DEST_ROOT / "candidate-a-vc-only", vc_mode="new", sp_mode="0.2.2")
    create_tree(DEST_ROOT / "candidate-b-sp021-only", vc_mode="baseline", sp_mode="0.2.1")
    create_tree(DEST_ROOT / "candidate-c-combined", vc_mode="new", sp_mode="0.2.1")
    print("\n[SUCCESS] All 4 candidate trees successfully prepared!", flush=True)

if __name__ == "__main__":
    main()
