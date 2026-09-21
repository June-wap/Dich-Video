"""Build a physical, application-owned Hugging Face model store for CP8.1B.

This intentionally copies only files required by the production loaders at
their immutable revisions.  Snapshot files are copied as ordinary files, not
symlinks to a developer's Hugging Face cache.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Artifact:
    provider: str
    repo_id: str
    revision: str
    filename: str
    sha256: str


VIENEU_REVISION = "7cbfde99a613d07630f390cc623ecfb2a070d0c1"
NEUCODEC_REVISION = "6f2b93b3fa2bc74740ba1bd10622e1ee37dbbe46"
DISTILHUBERT_REVISION = "fa87d96265d6b7af66e112faff6ff44df419cec9"
CHATTERBOX_REVISION = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"

# DistillNeuCodec constructs this exact semantic encoder internally.  Its
# three files are therefore a direct loader dependency, not an optional or
# unrelated cached model.
ARTIFACTS = (
    Artifact("vieneu", "pnnbao-ump/VieNeu-TTS", VIENEU_REVISION, "config.json", "250bc2c53c5c4e3962da12a9af1319d02d754f04ad718a703d26fb5d21c566be"),
    Artifact("vieneu", "pnnbao-ump/VieNeu-TTS", VIENEU_REVISION, "generation_config.json", "200d4713ccc78f9e018df4c92e79b9fc0b3bd0aeb9526e8bbd9fd8534cb194b1"),
    Artifact("vieneu", "pnnbao-ump/VieNeu-TTS", VIENEU_REVISION, "model.safetensors", "d142ffccf7983a04616a08456cd9f61632c86e76df1ef029461847b1129e2d45"),
    Artifact("vieneu", "pnnbao-ump/VieNeu-TTS", VIENEU_REVISION, "special_tokens_map.json", "c9b84b84227d009b296d633a6a4dc1c8aa318d851cbe308186014121e0cd1a46"),
    Artifact("vieneu", "pnnbao-ump/VieNeu-TTS", VIENEU_REVISION, "tokenizer.json", "74c466530bd698626a5b6a424d204711c58dfff0a6b3dd8b4dbac1e1e8c9aa87"),
    Artifact("vieneu", "pnnbao-ump/VieNeu-TTS", VIENEU_REVISION, "tokenizer_config.json", "058efca33cdb0e871f3e4f46c162cf3231e709129c0a024fb83317bffccd32f0"),
    Artifact("vieneu", "pnnbao-ump/VieNeu-TTS", VIENEU_REVISION, "vocab.json", "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"),
    Artifact("vieneu", "pnnbao-ump/VieNeu-TTS", VIENEU_REVISION, "voices.json", "555fc2e29507588b1ea6103b19c457350e1439296e48e03242b06969b128e9bf"),
    Artifact("neucodec", "neuphonic/distill-neucodec", NEUCODEC_REVISION, "pytorch_model.bin", "adace21f679b30f071c02e0cb3502d965ab08b50be936a5e81944674a5ae101e"),
    Artifact("neucodec", "neuphonic/distill-neucodec", NEUCODEC_REVISION, "meta.yaml", "232631816b83ee6c8929b7f0b960aedb7b215caa73dd96f7a0e60946b2a1319b"),
    Artifact("neucodec_semantic_encoder", "ntu-spml/distilhubert", DISTILHUBERT_REVISION, "config.json", "0427043d1c4c8d58298d2050420a0c2ce85c8b92ec3865eaecc62c3fc5a97006"),
    Artifact("neucodec_semantic_encoder", "ntu-spml/distilhubert", DISTILHUBERT_REVISION, "model.safetensors", "77ad8f985c97750d8d27d6950c917800d80732a141370bf316058bded71a6cbe"),
    Artifact("neucodec_semantic_encoder", "ntu-spml/distilhubert", DISTILHUBERT_REVISION, "preprocessor_config.json", "7a8f0fc8ee1272ed28a8b468e183c56a19329a92babd3ca8d4d21ae02ba511cd"),
    Artifact("chatterbox", "ResembleAI/chatterbox", CHATTERBOX_REVISION, "t3_mtl23ls_v3.safetensors", "5abca8321ede76f8e61f1cc0d19aea6c946b28871017ce8726f8a69203f05953"),
    Artifact("chatterbox", "ResembleAI/chatterbox", CHATTERBOX_REVISION, "s3gen.pt", "9b9ff07e60b20c136e2b1b3d7563a24604e8d2c4c267888d1ee929dd0151d2a3"),
    Artifact("chatterbox", "ResembleAI/chatterbox", CHATTERBOX_REVISION, "ve.pt", "4b16d836bc598509860f6fa068165a8bb5e9ac84f05582dfcf278a5a372879f1"),
    Artifact("chatterbox", "ResembleAI/chatterbox", CHATTERBOX_REVISION, "conds.pt", "6552d70568833628ba019c6b03459e77fe71ca197d5c560cef9411bee9d87f4e"),
    Artifact("chatterbox", "ResembleAI/chatterbox", CHATTERBOX_REVISION, "Cangjie5_TC.json", "7073fd9de919443ae88e0bd2449917a65fe54898a4413ed1edcc4b67f28bce8c"),
    Artifact("chatterbox", "ResembleAI/chatterbox", CHATTERBOX_REVISION, "grapheme_mtl_merged_expanded_v1.json", "69632f47220a788a52ce2661d096453c5655e9bf25289d89a8d832c46ee07dbf"),
)

# DistillNeuCodec requests this dependency without an explicit revision.  The
# standard HF cache uses refs/main to resolve that request to the audited
# snapshot while offline.  This is repository metadata, not a model artifact.
OFFLINE_REFS = {
    "ntu-spml/distilhubert": {"main": DISTILHUBERT_REVISION},
}


def _repo_cache_name(repo_id: str) -> str:
    return "models--" + repo_id.replace("/", "--")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stage(source_hub: Path, destination: Path) -> Path:
    """Copy verified source snapshots into ``destination/huggingface/hub``."""
    source_hub = source_hub.resolve(strict=True)
    destination = destination.resolve()
    hub_root = destination / "huggingface" / "hub"
    manifest = []

    for artifact in ARTIFACTS:
        relative = Path(_repo_cache_name(artifact.repo_id)) / "snapshots" / artifact.revision / artifact.filename
        source = (source_hub / relative).resolve(strict=True)
        if source.is_symlink() or not source.is_file():
            raise RuntimeError(f"Source artifact is not a physical file: {source}")
        actual = _sha256(source)
        if actual != artifact.sha256:
            raise RuntimeError(f"SHA256 mismatch for {artifact.repo_id}@{artifact.revision}/{artifact.filename}")

        target = hub_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if target.is_symlink() or target.resolve().is_relative_to(destination) is False:
            raise RuntimeError(f"Staged artifact escaped application store: {target}")
        if _sha256(target) != artifact.sha256:
            raise RuntimeError(f"Copied artifact SHA256 mismatch: {target}")
        manifest.append({
            "provider": artifact.provider,
            "repo_id": artifact.repo_id,
            "revision": artifact.revision,
            "relative_path": target.relative_to(destination).as_posix(),
            "size_bytes": target.stat().st_size,
            "sha256": artifact.sha256,
        })

    for repo_id, refs in OFFLINE_REFS.items():
        for name, revision in refs.items():
            ref_path = hub_root / _repo_cache_name(repo_id) / "refs" / name
            ref_path.parent.mkdir(parents=True, exist_ok=True)
            ref_path.write_text(revision, encoding="utf-8")

    manifest_path = destination / "model-manifest.json"
    manifest_path.write_text(json.dumps({"artifacts": manifest}, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-hub", type=Path, required=True, help="Existing HF hub cache; read only")
    parser.add_argument("--destination", type=Path, required=True, help="Application-owned model-store root")
    args = parser.parse_args()
    print(stage(args.source_hub, args.destination))


if __name__ == "__main__":
    main()
