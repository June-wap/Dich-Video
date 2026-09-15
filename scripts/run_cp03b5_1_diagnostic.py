"""CP0.3B-5.1 Diagnostic Script — Content Fidelity Investigation.

Captures per-chunk text, raw OmniVoice WAV, and DSP-processed WAV
for human listening comparison.  Must be run on a CUDA-capable host
with the full OmniVoice venv activated.

Usage:
    cd "d:\\Tool Dich Cho Khach"
    & "external\\OmniVoice\\.venv312\\Scripts\\python.exe" scripts/run_cp03b5_1_diagnostic.py
"""
from __future__ import annotations

import json
import logging
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "prototype"))

import numpy as np
import soundfile as sf
from pydub import AudioSegment

from core.audio_utils import (
    BoundaryDSPConfig, _trim_segment_safely, merge_segments, select_pause_ms,
)
from core.long_text import ChunkingConfig, build_chunks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("cp03b5_1")

DIAG = ROOT / "reports" / "cp03b5_1_diagnostic"
INPUT = ROOT / "reports" / "cp03b5_listening" / "input.txt"
REF = ROOT / "prototype" / "voices" / "e2_test" / "reference.wav"
FINAL = ROOT / "reports" / "cp03b5_listening" / "long_form.wav"
SR = 24000
