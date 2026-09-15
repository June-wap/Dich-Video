"""Prototype TTS Application — Gradio UI with 4 tabs."""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

# Ensure project root is on sys.path so relative imports work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROTO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROTO_ROOT))

# ── Logging setup ──
LOG_DIR = PROTO_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "prototype.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("prototype")

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

import gradio as gr
import numpy as np

from core.hardware import get_hardware_info, get_runtime_versions
from core.tts_manager import TTSManager
from core.audio_utils import wav_duration, export_mp3, merge_segments
from core.text_utils import (
    TEST_SENTENCES, VI_TEST_CASES, CONVERSATION_TEST, LANGUAGE_NAMES,
)


# ── Initialize providers & manager ──
def build_manager() -> TTSManager:
    mgr = TTSManager(PROJECT_ROOT)

    # 1) Sherpa-Piper for 8 espeak languages
    piper_models = PROJECT_ROOT / ".cp0" / "models" / "piper"
    espeak_data = (PROJECT_ROOT / ".cp0" / "models" / "sherpa"
                   / "vits-piper-vi_VN-vais1000-medium" / "espeak-ng-data")
    if piper_models.exists() and espeak_data.exists():
        from providers.sherpa_piper import SherpaPiperProvider
        mgr.register_provider(SherpaPiperProvider(piper_models, espeak_data))

    # 2) ORT-Direct for Japanese
    ja_model = PROJECT_ROOT / ".cp0" / "models" / "piper" / "ja_JA-hi_fi_captain-medium"
    if ja_model.exists():
        from providers.ort_japanese import ORTJapaneseProvider


        mgr.register_provider(ORTJapaneseProvider(ja_model))

    # 3) VieNeu cloning
    try:
        from providers.voice_clone import VieNeuCloneProvider
        mgr.register_provider(VieNeuCloneProvider())
    except Exception as e:
        logger.warning("VieNeu clone provider not available: %s", e)

    return mgr


manager = build_manager()

# ── Helper functions for UI ──
def get_lang_choices():
    langs = manager.get_languages()
    return [(f"{LANGUAGE_NAMES.get(l, l)} ({l})", l) for l in langs]


def get_voice_choices(language):
    if not language:
        return gr.update(choices=[], value=None)
    voices = manager.get_voice_display(language)
    if not voices:
        return gr.update(choices=[("Default", "default")], value="default")
    return gr.update(choices=voices, value=voices[0][1])


# ── TAB 1: Text to Speech ──
def tts_generate(language, voice_id, text, speed):
    if not isinstance(text, str) or not text.strip():
        return None, "Error: Please enter text.", None, None
    speed = float(speed) if speed else 1.0
    result = manager.synthesize(text, language, voice_id, speed=speed)
    if result.status != "PASS":
        return None, f"Error: {result.error}", None, None
    info = (
        f"Provider: {result.provider}\n"
        f"Model: {result.model}\n"
        f"Device: {result.device}\n"
        f"Generation time: {result.gen_time}s\n"
        f"Audio duration: {result.duration}s\n"
        f"RTF: {result.rtf}\n"
        f"Sample rate: {result.sample_rate} Hz\n"
        f"Status: {result.status}\nMP3: {result.export_error or 'PASS'}"
    )
    wav_path = result.wav_path
    mp3_path = getattr(result, "mp3_path", None)
    return wav_path, info, wav_path, mp3_path


# ── TAB 2: Conversation ──
def conversation_generate(turns_json):
    """Generate conversation from JSON turn list."""
    try:
        turns = json.loads(turns_json)
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}", None, None
    if not isinstance(turns, list) or not turns or any(not isinstance(t, dict) for t in turns):
        return None, "No turns provided.", None, None

    try:
        pauses = [float(t.get("pause_ms", 500)) for t in turns]
        if any(not np.isfinite(p) or p < 0 or p > 10000 for p in pauses):
            raise ValueError("Pause must be 0–10000 ms")
    except (TypeError, ValueError) as e:
        return None, str(e), None, None
    segment_paths = []
    status_lines = []
    for i, turn in enumerate(turns):
        speaker = turn.get("speaker", f"Speaker{i}")
        lang = turn.get("language", "vi")
        voice = turn.get("voice", "default")
        text = turn.get("text", "")
        if not isinstance(text, str) or not text.strip():
            status_lines.append(f"Turn {i+1} ({speaker}): SKIPPED (empty)")
            return None, "INVALID_TEXT: empty conversation turn", None, None

        ts = int(time.time() * 1000)
        fname = f"conv_turn{i}_{ts}.wav"
        result = manager.synthesize(text, lang, voice, filename=fname)
        if result.status == "PASS":
            segment_paths.append(result.wav_path)
            status_lines.append(
                f"Turn {i+1} ({speaker}): PASS | {result.duration}s | "
                f"RTF={result.rtf}")
        else:
            status_lines.append(
                f"Turn {i+1} ({speaker}): FAIL | {result.error}")
            return None, "\n".join(status_lines), None, None

    if not segment_paths:
        return None, "\n".join(status_lines), None, None

    ts = int(time.time() * 1000)
    merged_path = str(manager.output_dir / f"conversation_{ts}.wav")
    try:
        merge_segments(segment_paths, merged_path, pauses_ms=pauses)
    except Exception as e:
        return None, f"EXPORT_FAILED: {e}", None, None
    mp3_path = export_mp3(merged_path)
    if not mp3_path:
        status_lines.append("EXPORT_FAILED: MP3 failed; WAV retained")
    status_lines.append(f"\nMerged: {len(segment_paths)} segments -> {merged_path}")
    return merged_path, "\n".join(status_lines), merged_path, str(mp3_path) if mp3_path else None


# ── TAB 3: Voice Cloning ──
def clone_generate(ref_audio, voice_name, language, text):
    if ref_audio is None:
        return None, "Error: Please upload a reference audio file.", None, None
    if not isinstance(text, str) or not text.strip():
        return None, "Error: Please enter text to synthesize.", None, None

    # Get reference info
    try:
        ref_dur = wav_duration(ref_audio)
    except Exception:
        ref_dur = 0.0

    profile = manager.prepare_clone_profile(ref_audio)
    if profile.get("error"):
        return None, f"INVALID_REFERENCE_AUDIO: {profile['error']}", None, None
    ts = int(time.time() * 1000)
    fname = f"clone_{ts}.wav"
    result = manager.synthesize_clone(text, ref_audio, language=language,
                                      filename=fname, profile=profile)
    if result.status != "PASS":
        return None, f"Error: {result.error}", None, None

    info = (
        f"Reference duration: {ref_dur:.1f}s\n"
        f"Device: {result.device}\n"
        f"Model: {result.model}\n"
        f"Prep time: {profile.get('prep_time', 'N/A')}s\n"
        f"Generation time: {result.gen_time}s\n"
        f"Audio duration: {result.duration}s\n"
        f"RTF: {result.rtf}\n"
        f"Status: {result.status}\nMP3: {result.export_error or 'PASS'}"
    )
    mp3_path = getattr(result, "mp3_path", None)
    return result.wav_path, info, result.wav_path, mp3_path


# ── TAB 4: Diagnostics ──
def get_diagnostics():
    hw = get_hardware_info()
    rv = get_runtime_versions()
    health = manager.get_all_health()

    lines = ["═══ SYSTEM ═══"]
    lines.append(f"OS: {hw['os']}")
    lines.append(f"Python: {hw['python']}")
    lines.append(f"CPU: {hw['cpu']}")
    lines.append(f"Cores: {hw['cpu_cores_physical']}P / {hw['cpu_cores_logical']}L")
    lines.append(f"RAM: {hw['ram_available_gb']}/{hw['ram_total_gb']} GB")
    lines.append(f"GPU: {hw.get('gpu_name') or 'None detected'}")
    lines.append(f"CUDA: {hw['cuda_available']}")
    if hw.get("vram_total_gb"):
        lines.append(f"VRAM: {hw['vram_used_gb']}/{hw['vram_total_gb']} GB")

    lines.append("\n═══ RUNTIME VERSIONS ═══")
    for pkg, ver in rv.items():
        lines.append(f"{pkg}: {ver}")

    lines.append("\n═══ PROVIDERS ═══")
    for h in health:
        lines.append(f"\n[{h.get('provider', '?')}]")
        lines.append(f"  Status: {h.get('status', '?')}")
        if "available_languages" in h:
            lines.append(f"  Languages: {h['available_languages']}")
        if "model_path" in h:
            lines.append(f"  Model: {h['model_path']}")
        if "available" in h:
            lines.append(f"  Available: {h['available']}")

    lines.append("\n═══ INSTALLED MODELS ═══")
    models_dir = PROJECT_ROOT / ".cp0" / "models" / "piper"
    if models_dir.exists():
        for d in sorted(models_dir.iterdir()):
            if d.is_dir():
                onnx = d / f"{d.name}.onnx"
                status = "✓ installed" if onnx.exists() else "✗ missing"
                lines.append(f"  {d.name}: {status} | provider=Piper/ORT | path={onnx} | revision=unknown")

    return "\n".join(lines)


def run_self_test():
    results = manager.run_self_test()
    lines = ["═══ SELF-TEST RESULTS ═══\n"]
    for r in results:
        lang = r.get("language", "?")
        status = r.get("status", "?")
        icon = "✓" if status == "PASS" else "✗"
        line = f"{icon} {LANGUAGE_NAMES.get(lang, lang)} ({lang}): {status}"
        if status == "PASS":
            line += f" | {r.get('duration', 0)}s | RTF={r.get('rtf', 0)}"
        else:
            line += f" | {r.get('error', 'unknown error')}"
        lines.append(line)

    passed = sum(1 for r in results if r.get("status") == "PASS")
    lines.append(f"\nTotal: {passed}/{len(results)} PASS")
    return "\n".join(lines)



# ── Build Gradio UI ──
def create_app():
    lang_choices = get_lang_choices()
    default_lang = lang_choices[0][1] if lang_choices else None

    # Default conversation JSON
    default_conv = json.dumps([
        {"speaker": "A", "language": "vi", "voice": "vieneu:Trúc Ly",
         "text": "Xin chào, bạn có khỏe không?"},
        {"speaker": "B", "language": "vi", "voice": "vieneu:Minh Đức",
         "text": "Chào bạn, tôi khỏe. Cảm ơn bạn."},
        {"speaker": "A", "language": "vi", "voice": "vieneu:Trúc Ly",
         "text": "Hôm nay thời tiết đẹp quá nhỉ?"},
        {"speaker": "B", "language": "vi", "voice": "vieneu:Minh Đức",
         "text": "Đúng rồi, chúng ta đi dạo công viên đi."},
    ], ensure_ascii=False, indent=2)

    with gr.Blocks(title="Local AI Voice — Prototype", analytics_enabled=False) as app:
        gr.Markdown("# 🔊 Local AI Voice — Function Test Prototype")
        gr.Markdown("Offline TTS prototype: 9 languages, voice cloning, conversation mode.")

        # ── TAB 1: Text to Speech ──
        with gr.Tab("Text to Speech"):
            with gr.Row():
                with gr.Column(scale=1):
                    lang_dd = gr.Dropdown(
                        choices=lang_choices, value=default_lang,
                        label="Language", interactive=True)
                    voice_dd = gr.Dropdown(
                        choices=manager.get_voice_display(default_lang), value=(manager.get_voices(default_lang)[0].id if default_lang else None), label="Voice", interactive=True)
                    speed_sl = gr.Slider(
                        minimum=0.5, maximum=2.0, value=1.0, step=0.1,
                        label="Speed")
                with gr.Column(scale=2):
                    text_input = gr.Textbox(
                        label="Text",
                        placeholder="Enter text to synthesize...",
                        lines=4,
                        value=TEST_SENTENCES.get("vi", ""))
                    gen_btn = gr.Button("Generate", variant="primary")

            info_box = gr.Textbox(label="Info", lines=6, interactive=False)
            audio_out = gr.Audio(label="Generated Audio", type="filepath")
            with gr.Row():
                wav_dl = gr.File(label="Download WAV")
                mp3_dl = gr.File(label="Download MP3")

            # Wire events
            lang_dd.change(get_voice_choices, inputs=[lang_dd], outputs=[voice_dd])
            gen_btn.click(
                tts_generate,
                inputs=[lang_dd, voice_dd, text_input, speed_sl],
                outputs=[audio_out, info_box, wav_dl, mp3_dl])

        # ── TAB 2: Conversation ──
        with gr.Tab("Conversation"):
            gr.Markdown("Define conversation turns as JSON. Each turn: "
                        "`speaker`, `language`, `voice`, `text`, `pause_ms` (0–10000).")
            conv_input = gr.Textbox(
                label="Conversation Turns (JSON)",
                lines=12, value=default_conv)
            conv_btn = gr.Button("Generate Conversation", variant="primary")
            conv_status = gr.Textbox(label="Status", lines=8, interactive=False)
            conv_audio = gr.Audio(label="Merged Audio", type="filepath")
            with gr.Row():
                conv_wav_dl = gr.File(label="Download WAV")
                conv_mp3_dl = gr.File(label="Download MP3")
            conv_btn.click(
                conversation_generate, inputs=[conv_input],
                outputs=[conv_audio, conv_status, conv_wav_dl, conv_mp3_dl])

        # ── TAB 3: Voice Cloning ──
        with gr.Tab("Voice Cloning"):
            gr.Markdown("Reference transcript is not required by VieNeu v3 Turbo. Use audio you have permission to use.")
            gr.Markdown("Upload a reference audio file and synthesize with "
                        "cloned voice (VieNeu v3 Turbo).")
            with gr.Row():
                with gr.Column(scale=1):
                    ref_audio = gr.Audio(
                        label="Reference Audio (WAV/MP3)",
                        type="filepath")
                    clone_name = gr.Textbox(
                        label="Voice Name", value="my_clone")
                    clone_lang = gr.Dropdown(
                        choices=[("Vietnamese", "vi")],
                        value="vi", label="Language")
                with gr.Column(scale=2):
                    clone_text = gr.Textbox(
                        label="Text to Synthesize", lines=4,
                        value="Xin chào, đây là bài kiểm tra chức năng "
                              "nhân bản giọng nói chạy hoàn toàn trên máy tính.")
                    clone_btn = gr.Button("Generate Clone", variant="primary")

            clone_info = gr.Textbox(label="Clone Info", lines=6, interactive=False)
            clone_audio = gr.Audio(label="Cloned Audio", type="filepath")
            with gr.Row():
                clone_wav_dl = gr.File(label="Download WAV")
                clone_mp3_dl = gr.File(label="Download MP3")
            clone_btn.click(
                clone_generate,
                inputs=[ref_audio, clone_name, clone_lang, clone_text],
                outputs=[clone_audio, clone_info, clone_wav_dl, clone_mp3_dl])

        # ── TAB 4: Diagnostics ──
        with gr.Tab("Diagnostics"):
            diag_btn = gr.Button("Refresh Diagnostics")
            diag_box = gr.Textbox(label="System & Model Status", lines=20,
                                  interactive=False)
            diag_btn.click(get_diagnostics, outputs=[diag_box])

            gr.Markdown("---")
            test_btn = gr.Button("Run TTS Self-Test", variant="primary")
            test_box = gr.Textbox(label="Self-Test Results", lines=15,
                                  interactive=False)
            test_btn.click(run_self_test, outputs=[test_box])

    return app


# ── Main entry ──
if __name__ == "__main__":
    logger.info("Starting Local AI Voice Prototype...")
    app = create_app()
    app.launch(server_name="127.0.0.1", server_port=7860, share=False)


