import sys
from pathlib import Path
import json
import logging
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from prototype.core.long_text import build_chunks, ChunkingConfig
from prototype.providers.omnivoice import OmniVoiceProvider
from prototype.core.audio_utils import BoundaryDSPConfig, merge_segments, _trim_segment_safely

logging.basicConfig(level=logging.INFO)

def main():
    root_dir = Path(__file__).parent.parent
    reports_dir = root_dir / "reports"
    input_file = reports_dir / "cp03b5_listening" / "input.txt"
    diagnostic_dir = reports_dir / "cp03b5_1_diagnostic"
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    
    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read()

    chunks = build_chunks(text, ChunkingConfig())
    print(f"Total chunks expected: {len(chunks)}")
    
    # We will initialize OmniVoiceProvider
    provider = OmniVoiceProvider()
    provider._load_model()
    
    # Load profile
    reference_path = root_dir / "prototype" / "voices" / "e2_test" / "reference.wav"
    profile_result = provider.prepare_voice_profile(reference_path)
    if "error" in profile_result:
        print("Profile error:", profile_result["error"])
        return
    profile = profile_result["profile"]

    segment_paths = []
    
    for i, chunk in enumerate(chunks):
        chunk_dir = diagnostic_dir / f"chunk_{i:03d}"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        
        # Save text
        (chunk_dir / "text.txt").write_text(chunk.text, encoding="utf-8")
        
        raw_path = chunk_dir / "raw.wav"
        
        # Synthesize raw
        print(f"Synthesizing chunk {i}: {chunk.text[:30]}...")
        result = provider.synthesize_cloned(
            text=chunk.text,
            language="vi",
            profile=profile,
            output_path=str(raw_path)
        )
        if result.status != "PASS":
            print(f"Failed to generate chunk {i}: {result.error}")
        else:
            segment_paths.append(raw_path)

    # Now let's run DSP and save processed.wav for each chunk
    from pydub import AudioSegment
    
    config = BoundaryDSPConfig()
    
    for i, raw_path in enumerate(segment_paths):
        chunk_dir = diagnostic_dir / f"chunk_{i:03d}"
        processed_path = chunk_dir / "processed.wav"
        
        seg = AudioSegment.from_wav(str(raw_path))
        target_sr = 24000
        if seg.frame_rate != target_sr:
            seg = seg.set_frame_rate(target_sr)
        if seg.channels != 1:
            seg = seg.set_channels(1)
            
        seg, trim_leading, trim_trailing = _trim_segment_safely(seg, config)
        
        gain_db = 0.0
        if config.target_dbfs is not None and seg.dBFS != float("-inf"):
            gain_db = max(-config.max_gain_db, min(config.max_gain_db, config.target_dbfs - seg.dBFS))
            seg = seg.apply_gain(gain_db)
            
        fade = min(config.edge_fade_ms, len(seg) // 2)
        if fade:
            seg = seg.fade_in(fade).fade_out(fade)
            
        seg.export(str(processed_path), format="wav")
        print(f"Saved processed chunk {i}")
        
    print("All chunks synthesized and DSP applied.")

if __name__ == "__main__":
    main()
