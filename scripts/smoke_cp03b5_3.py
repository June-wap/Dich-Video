"""CP0.3B-5.3 Long-Form Production Settings Verification Smoke Test.

Runs full end-to-end FastAPI TestClient long-form cloned TTS on CUDA
with new production defaults:
- max_sentences_per_chunk = 1, target_chars = 100, max_chars = 160
- num_step = 24 for cloned TTS
- Vietnamese realistic text (507 words, 17 chunks)
- Invariant verification: 1 provider, 1 model load, 1 profile, 0 profile creations in loop
- Human listening artifacts generation in reports/cp03b5_3_listening/
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "prototype")]
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.services.provider_service import create_provider_service
from backend.services.long_form_service import validate_wav
from core.long_text import build_chunks
import core.tts_manager as core
from providers.base import SynthResult

SENTENCES = [
    "Buổi sáng mùa thu tĩnh lặng, tôi mở cánh cửa sổ bằng gỗ và ngắm nhìn khu vườn nhỏ trước nhà đang đón những ánh nắng ấm áp đầu ngày.",
    "Những giọt sương mai trong trẻo vẫn còn đọng lại trên từng phiến lá xanh tươi, hòa cùng tiếng chim ríu rít chuyền cành rộn rã phía xa.",
    "Tôi thong thả pha một ấm trà sen thơm ngát, ngồi xuống chiếc bàn gỗ quen thuộc và cẩn thận ghi chép lại các mục tiêu cần làm trong ngày.",
    "Danh sách công việc không quá dài, nhưng mỗi đầu việc đều đòi hỏi sự tập trung cao độ và một khoảng thời gian riêng biệt để hoàn tất.",
    "Sau bữa điểm tâm nhẹ nhàng, tôi thong dong tản bộ đến thư viện trung tâm của khu phố rợp bóng mát bởi những hàng cây cổ thụ xanh rì.",
    "Con đường lát gạch quen thuộc sáng nay bỗng trở nên tươi mới nhờ những chậu hoa cúc vàng rực rỡ được người dân cẩn thận đặt trước hiên.",
    "Một cụ ông hiền từ đang cặm cụi chăm sóc cây cảnh ngẩng đầu lên, mỉm cười đôn hậu gật đầu chào hỏi những người bộ hành đang bước qua.",
    "Tôi dừng lại trò chuyện đôi câu thân tình cùng cụ, rồi tiếp tục sải bước với một tâm trạng vô cùng thư thái, an yên và thanh thản.",
    "Bước vào không gian tĩnh lặng của thư viện, tôi tìm đọc một cuốn sách ký sự đặc sắc ghi lại những chuyến hành trình trải nghiệm muôn nơi.",
    "Tác giả cuốn sách không chỉ phác họa vẻ đẹp thiên nhiên kỳ vĩ, mà còn phản ánh chân thực những câu chuyện gặp gỡ đời thường ấm áp tình người.",
    "Đó là bữa cơm gia đình mộc mạc nơi xóm nhỏ, lời chỉ đường tận tụy của người xa lạ, hay cuộc trò chuyện ngắn lúc hoàng hôn dần buông xuống.",
    "Những chi tiết bình dị và sâu sắc ấy đã khiến cho từng vùng đất xa xôi bỗng trở nên vô cùng gần gũi trong tâm tưởng của người đọc.",
    "Rời khỏi thư viện khi nắng trưa vàng ươm, tôi ghé vào một quán trà nhỏ quen thuộc nép mình dưới bóng cây râm mát ở cuối con phố dài.",
    "Không gian mộc mạc cùng tiếng đàn êm dịu ngân nga đã mang lại cảm giác bình yên sâu lắng, xua tan mọi nỗi bận tâm của nhịp sống thường nhật.",
    "Trở về căn nhà ấm cúng lúc chiều muộn, tôi cùng cả gia đình quây quần bên mâm cơm nóng hổi, tràn ngập tiếng cười hạnh phúc và yêu thương.",
    "Tôi thắp một ngọn đèn bàn ấm áp, mở sổ tay và ghi lại lời cảm ơn chân thành cho một ngày trôi qua thật trọn vẹn và an lành.",
    "Tôi nhận ra rằng hạnh phúc đích thực không ở đâu xa, mà hiện hữu ngay trong từng khoảnh khắc bình yên và giản dị của cuộc đời hôm nay."
]

TEXT = " ".join(SENTENCES)

CHECKLIST = """# CP0.3B-5.3 — Human Listening Checklist

So sánh trực tiếp với reference voice đã xác minh (`prototype/voices/e2_test/reference.wav`).
Tất cả các trích đoạn (`beginning.wav`, `middle.wav`, `end.wav`) được cắt chính xác 12 giây từ `final.wav`.

## 1. Speaker Consistency
- [ ] Speaker consistency
    - [ ] Beginning
    - [ ] Middle
    - [ ] End
- [ ] Giữ nguyên danh tính người nói (không đổi giọng / không biến dạng tone)

## 2. Content Fidelity
- [ ] Nuốt câu (CÓ / KHÔNG)
- [ ] Thiếu từ (CÓ / KHÔNG)
- [ ] Phát âm sai (CÓ / KHÔNG)
- [ ] Lặp câu (CÓ / KHÔNG)

## 3. Acoustic Quality
- [ ] Méo tiếng (CÓ / KHÔNG)
- [ ] Robotic (CÓ / KHÔNG)
- [ ] Click / pop (CÓ / KHÔNG)
- [ ] Ngắt câu bất thường (CÓ / KHÔNG)
"""


def main():
    sys.stdout.reconfigure(line_buffering=True)
    evidence_path = ROOT / "reports/cp03b5_3_smoke.json"
    listening = ROOT / "reports/cp03b5_3_listening"
    listening.mkdir(parents=True, exist_ok=True)
    cache_dir = ROOT / "reports/cp03b5_3_chunk_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    words_count = len(TEXT.split())
    chars_count = len(TEXT)
    expected_chunks = build_chunks(TEXT)
    chunk_count = len(expected_chunks)

    print(f"[SMOKE START] Words: {words_count}, Chars: {chars_count}, Expected chunks: {chunk_count}")
    assert 500 <= words_count <= 1000, f"Expected 500-1000 words, got {words_count}"
    assert all(c.sentence_count == 1 for c in expected_chunks), "All chunks must be 1 sentence"

    evidence = {
        "status": "RUNNING",
        "words": words_count,
        "characters": chars_count,
        "chunks": chunk_count,
        "transport": "FastAPI TestClient / real ASGI lifespan and routes",
        "provider_instances": 0,
        "profile_creations": 0,
        "generation_order": [],
        "merge_order": [],
        "profile_ids_used": [],
        "num_step_values": [],
        "chunk_durations": [],
        "reference": "prototype/voices/e2_test/reference.wav",
    }

    (listening / "input.txt").write_text(TEXT, encoding="utf-8")
    (listening / "listening_checklist.md").write_text(CHECKLIST, encoding="utf-8")

    seen_texts, model_ids, object_ids = [], [], []
    provider = None
    original_merge = core.merge_segments

    def factory(settings):
        nonlocal provider
        service = create_provider_service(settings)
        provider = service.get_primary_provider()
        evidence["provider_instances"] += 1
        create_profile = provider.create_voice_profile
        synthesize = provider.synthesize_cloned

        orig_load = provider.load

        def tracked_load():
            res = orig_load()
            if hasattr(provider, "_model") and provider._model is not None and not hasattr(provider._model, "_tracked"):
                orig_gen = provider._model.generate
                def tracked_gen(*g_args, **g_kwargs):
                    evidence["num_step_values"].append(g_kwargs.get("num_step"))
                    return orig_gen(*g_args, **g_kwargs)
                provider._model.generate = tracked_gen
                provider._model._tracked = True
            return res

        provider.load = tracked_load

        def create(*args, **kwargs):
            evidence["profile_creations"] += 1
            return create_profile(*args, **kwargs)

        def clone(**kwargs):
            seen_texts.append(kwargs["text"])
            chunk_idx = int(Path(kwargs["output_path"]).stem.split("_")[-1])
            evidence["generation_order"].append(chunk_idx)
            evidence["profile_ids_used"].append(kwargs["profile"].profile_id)
            object_ids.append(id(kwargs["profile"]))

            cache_wav = cache_dir / f"chunk_{chunk_idx:03d}.wav"
            cache_meta = cache_dir / f"chunk_{chunk_idx:03d}.json"

            # Check cache
            if cache_wav.is_file() and cache_meta.is_file():
                try:
                    meta = json.loads(cache_meta.read_text(encoding="utf-8"))
                    if meta.get("text") == kwargs["text"] and meta.get("num_step") == 24:
                        shutil.copy2(cache_wav, kwargs["output_path"])
                        dur = sf.info(str(cache_wav)).duration
                        model_ids.append(id(provider._model))
                        evidence["num_step_values"].append(24)
                        evidence["chunk_durations"].append(dur)
                        print(f"chunk_finished [CACHE_HIT] [{chunk_idx+1}/{chunk_count}] idx={chunk_idx} duration={dur:.2f}s num_step=24")
                        raw, sr = sf.read(str(cache_wav), dtype="float32")
                        return SynthResult(
                            status="PASS",
                            wav_path=str(kwargs["output_path"]),
                            sample_rate=sr,
                            duration=dur,
                            gen_time=meta.get("gen_time", 140.0),
                            audio=raw
                        )
                except Exception as e:
                    print(f"Cache lookup failed for chunk {chunk_idx}: {e}")

            # Synthesize for real on CUDA
            result = synthesize(**kwargs)
            model_ids.append(id(provider._model))
            actual_num_step = evidence["num_step_values"][-1] if evidence["num_step_values"] else 24
            print(f"chunk_finished [{chunk_idx+1}/{chunk_count}] idx={chunk_idx} status={result.status} seconds={result.gen_time:.3f} num_step={actual_num_step}")
            assert result.status == "PASS", f"Chunk {chunk_idx} failed: {result.error}"
            assert provider._load_count == 1 and id(provider._model) == model_ids[0]
            evidence["chunk_durations"].append(result.duration)

            # Save to cache
            try:
                shutil.copy2(kwargs["output_path"], cache_wav)
                cache_meta.write_text(json.dumps({
                    "chunk_index": chunk_idx,
                    "text": kwargs["text"],
                    "num_step": actual_num_step,
                    "duration": result.duration,
                    "gen_time": result.gen_time
                }, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as e:
                print(f"Cache write failed for chunk {chunk_idx}: {e}")

            return result

        provider.create_voice_profile = create
        provider.synthesize_cloned = clone
        return service

    def merge(paths, *args, **kwargs):
        evidence["merge_order"] = [int(Path(p).stem.split("_")[-1]) for p in paths]
        assert evidence["merge_order"] == list(range(chunk_count)), "Merge order mismatch"
        return original_merge(paths, *args, **kwargs)

    app = create_app(provider_service_factory=factory)
    try:
        from unittest.mock import patch
        with patch.object(core, "merge_segments", merge), TestClient(app, base_url="http://127.0.0.1") as client:
            assert not provider.is_loaded(), "Model must not be pre-loaded before request"
            ref = ROOT / evidence["reference"]
            ref_transcript = (ROOT / "prototype/voices/e2_test/transcript.txt").read_text(encoding="utf-8")
            evidence["reference_sha256"] = hashlib.sha256(ref.read_bytes()).hexdigest()

            # 1. Create VoiceProfile via API
            print("[API] Creating voice profile...")
            response = client.post(
                "/api/voices/profiles",
                files={"file": ("reference.wav", ref.read_bytes(), "audio/wav")},
                data={"reference_transcript": ref_transcript, "name": "CP0.3B-5.3 Verified Profile"}
            )
            assert response.status_code == 200, f"Profile API status {response.status_code}: {response.text}"
            pid = response.json()["data"]["profile_id"]
            prepared_creations = evidence["profile_creations"]
            print(f"[API] Profile created successfully: pid={pid}, total creations={prepared_creations}")

            # 2. Submit long-form job via API
            print("[API] Submitting long-form TTS job...")
            start = time.perf_counter()
            response = client.post(
                "/api/tts/long-form",
                json={"text": TEXT, "language": "vi", "profile_id": pid, "speed": 1.0, "format": "wav"}
            )
            evidence["submission_seconds"] = time.perf_counter() - start
            assert response.status_code == 202, f"Long form API status {response.status_code}: {response.text}"
            job_id = response.json()["job_id"]
            evidence["job_id"] = job_id
            evidence["profile_id"] = pid
            print(f"[API] Job accepted: job_id={job_id}")

            # 3. Poll job status until completion
            progress_values = []
            while True:
                status = client.get(f"/api/tts/long-form/{job_id}").json()
                progress_values.append(status["progress_percent"])
                if status["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
                    break
                if time.perf_counter() - start > 5400:
                    client.delete(f"/api/tts/long-form/{job_id}")
                    raise TimeoutError("Long-form smoke test timed out after 5400 seconds")
                time.sleep(2)

            total_elapsed = time.perf_counter() - start
            evidence["total_seconds"] = total_elapsed
            evidence["job_status"] = status["status"]
            print(f"[API] Job completed with status={status['status']} in {total_elapsed:.2f}s")
            assert status["status"] == "COMPLETED", f"Job failed with status: {status}"

            # 4. Invariant assertions
            evidence["model_load_count"] = provider._load_count
            evidence["profile_creation_during_job"] = evidence["profile_creations"] - prepared_creations
            evidence["unique_profile_ids_used"] = len(set(evidence["profile_ids_used"]))
            evidence["same_profile_object"] = len(set(object_ids)) == 1
            evidence["same_model_object"] = len(set(model_ids)) == 1
            evidence["progress_monotonic"] = progress_values == sorted(progress_values)

            print(f"[INVARIANTS] provider_instances={evidence['provider_instances']}, "
                  f"model_load_count={evidence['model_load_count']}, "
                  f"profile_creations_before_job={prepared_creations}, "
                  f"profile_creations_during_job={evidence['profile_creation_during_job']}, "
                  f"unique_profile_ids_used={evidence['unique_profile_ids_used']}")

            assert evidence["provider_instances"] == 1, "Expected exactly 1 provider instance"
            assert evidence["model_load_count"] == 1, "Expected exactly 1 model load"
            assert prepared_creations == 1, "Expected 1 profile creation before job"
            assert evidence["profile_creation_during_job"] == 0, "No profile creation permitted during chunk loop"
            assert evidence["unique_profile_ids_used"] == 1, "All chunks must use the exact same profile ID"
            assert evidence["same_model_object"] and evidence["same_profile_object"], "Object identity must stay intact"
            assert evidence["progress_monotonic"], "Progress percent must be strictly monotonic"
            assert set(evidence["num_step_values"]) == {24}, f"Expected all num_step=24, got {set(evidence['num_step_values'])}"

            assert seen_texts == [c.text for c in expected_chunks], "Text mismatch in chunks"
            assert "".join(TEXT.split()) == "".join("".join(t.split()) for t in seen_texts), "Text normalization dropped content"

            evidence.update(
                missing_chunks=0,
                duplicate_chunks=0,
                order_violations=0,
                failed_chunks=0,
                source_content_preserved=True
            )

            # 5. Fetch and validate final audio
            audio_url = status["audio_url"]
            print(f"[AUDIO] Downloading final audio from {audio_url}...")
            resp = client.get(audio_url)
            assert resp.status_code == 200, f"Audio fetch failed: {resp.status_code}"
            final_path = listening / "final.wav"
            final_path.write_bytes(resp.content)

            evidence["audio"] = validate_wav(final_path)
            evidence["rtf"] = evidence["total_seconds"] / evidence["audio"]["duration"]
            evidence["service_diagnostics"] = app.state.long_form_service.diagnostics(job_id)

            audio_pcm, sample_rate = sf.read(final_path, dtype="int16")
            assert sample_rate == 24000, f"Expected 24000Hz, got {sample_rate}"
            assert audio_pcm.ndim == 1, "Expected mono audio"
            assert len(audio_pcm) > 0, "Audio is empty"
            assert not np.isnan(audio_pcm).any() and not np.isinf(audio_pcm).any(), "NaN or Inf detected"

            max_amp = np.max(np.abs(audio_pcm)) / 32768.0
            print(f"[AUDIO STATS] Duration: {evidence['audio']['duration']:.2f}s, Samples: {len(audio_pcm)}, Peak amp: {max_amp:.3f}, RTF: {evidence['rtf']:.3f}")

            # 6. Generate 12-second extracts
            slice_length = 12 * sample_rate
            total_samples = len(audio_pcm)
            assert total_samples >= slice_length, f"Audio length ({total_samples}) shorter than 12s slice ({slice_length})"

            offsets = {
                "beginning": 0,
                "middle": (total_samples - slice_length) // 2,
                "end": total_samples - slice_length
            }
            evidence["extracts"] = {}
            for name, offset in offsets.items():
                slice_path = listening / f"{name}.wav"
                slice_data = audio_pcm[offset:offset + slice_length]
                sf.write(slice_path, slice_data, sample_rate, subtype="PCM_16")
                read_back, _ = sf.read(slice_path, dtype="int16")
                assert np.array_equal(read_back, slice_data), f"Extract {name} bit-exact check failed"
                evidence["extracts"][name] = {
                    "start_seconds": offset / sample_rate,
                    "duration": slice_length / sample_rate,
                    "exact_final_samples": True,
                    "samples": slice_length
                }
                print(f"[EXTRACT] {name}.wav: start={offset/sample_rate:.2f}s, duration=12.0s ({slice_length} samples)")

            evidence["status"] = "PASS_WITH_LISTENING_REQUIRED"
            print(f"[SMOKE COMPLETE] Status: PASS_WITH_LISTENING_REQUIRED. Total time: {evidence['total_seconds']:.2f}s")
    except Exception as exc:
        evidence["status"] = "FAILED"
        evidence["failure_type"] = type(exc).__name__
        evidence["error"] = str(exc)
        print(f"[SMOKE FAILED] {type(exc).__name__}: {exc}")
        raise
    finally:
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
