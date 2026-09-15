"""Patch Japanese Piper ONNX model to add Sherpa-required metadata."""
import json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = ROOT / '.cp0/models/piper/ja_JA-hi_fi_captain-medium/ja_JA-hi_fi_captain-medium.onnx'
dst = ROOT / '.cp0/models/piper/ja_JA-hi_fi_captain-medium/ja_JA-hi_fi_captain-medium_sherpa.onnx'

# Read JSON config for metadata
cfg_path = ROOT / '.cp0/models/piper/ja_JA-hi_fi_captain-medium/ja_JA-hi_fi_captain-medium.onnx.json'
with open(cfg_path) as f:
    cfg = json.load(f)

import onnx
model = onnx.load(str(src))

# Add required metadata for Sherpa-ONNX
metadata = {
    "model_type": "vits",
    "comment": "piper",
    "language": "Japanese",
    "has_espeak": "1",
    "voice": "ja",
    "n_speakers": str(cfg.get("num_speakers", 2)),
    "sample_rate": str(cfg["audio"]["sample_rate"]),
}

# Clear existing metadata and add new
while model.metadata_props:
    model.metadata_props.pop()

for k, v in metadata.items():
    entry = model.metadata_props.add()
    entry.key = k
    entry.value = v

onnx.save(model, str(dst))
print(f"Patched model saved to: {dst}")
print(f"Size: {dst.stat().st_size} bytes")

# Verify
import onnxruntime as ort
sess = ort.InferenceSession(str(dst), providers=["CPUExecutionProvider"])
meta = sess.get_modelmeta().custom_metadata_map
print(f"Metadata: {meta}")
