import time
import torch
import torchaudio

from chatterbox.mtl_tts import ChatterboxMultilingualTTS

if not torch.cuda.is_available():
    raise RuntimeError("CUDA is required for CP4. CPU fallback is forbidden.")

device = "cuda"

print("=== CP4 CHATTERBOX MULTILINGUAL V3 REAL TEST ===")
print("torch:", torch.__version__)
print("cuda:", torch.version.cuda)
print("gpu:", torch.cuda.get_device_name(0))
print(
    "vram_total_gb:",
    round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2),
)

torch.cuda.empty_cache()
torch.cuda.reset_peak_memory_stats()

print("\nLoading Chatterbox Multilingual V3...")

torch.cuda.synchronize()
start = time.perf_counter()

model = ChatterboxMultilingualTTS.from_pretrained(
    device=device,
    t3_model="v3",
)

torch.cuda.synchronize()
load_seconds = time.perf_counter() - start

print("V3 load PASS")
print("load_seconds:", round(load_seconds, 2))

text = "This is a real Chatterbox Multilingual V3 synthesis test."

print("\nGenerating English audio...")

torch.cuda.synchronize()
start = time.perf_counter()

wav = model.generate(
    text,
    language_id="en",
)

torch.cuda.synchronize()
synth_seconds = time.perf_counter() - start

output = "cp4_chatterbox_v3_en.wav"

torchaudio.save(
    output,
    wav.cpu(),
    model.sr,
)

peak_allocated = torch.cuda.max_memory_allocated() / 1024**3
peak_reserved = torch.cuda.max_memory_reserved() / 1024**3

print("\n=== RESULT ===")
print("model: Chatterbox Multilingual V3")
print("t3_model: v3")
print("language: en")
print("sample_rate:", model.sr)
print("load_seconds:", round(load_seconds, 2))
print("synthesis_seconds:", round(synth_seconds, 2))
print("peak_allocated_gb:", round(peak_allocated, 2))
print("peak_reserved_gb:", round(peak_reserved, 2))
print("output:", output)
print("CP4 REAL INFERENCE PASS")
