"""One real CUDA long-form job via ASGI API; no regenerated listening extracts."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

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

TEXT = """Buổi sáng, tôi mở cửa sổ và nhìn khu vườn nhỏ trước nhà. Những giọt nước còn đọng trên lá, trong khi tiếng chim vang lên từ hàng cây phía xa. Tôi pha một tách trà, ngồi xuống bàn và viết ra những việc cần làm trong ngày. Danh sách không dài, nhưng mỗi việc đều cần sự chú ý và một khoảng thời gian riêng để hoàn thành.

Sau bữa sáng, tôi đi bộ đến thư viện gần khu phố. Con đường quen thuộc hôm nay có thêm vài chậu hoa mới, được người dân đặt ngay trước hiên nhà. Một bác lớn tuổi đang tưới cây và mỉm cười chào những người đi ngang qua. Tôi dừng lại trò chuyện một chút, rồi tiếp tục bước đi với cảm giác nhẹ nhàng và thư thái hơn lúc mới rời nhà.

Ở thư viện, tôi chọn một cuốn sách kể về những chuyến đi qua nhiều vùng đất khác nhau. Tác giả không chỉ miêu tả cảnh đẹp mà còn ghi lại những cuộc gặp gỡ rất bình thường. Đó có thể là một bữa cơm cùng gia đình xa lạ, một lời chỉ đường tận tình, hoặc câu chuyện ngắn bên quán nước ven đường. Những chi tiết nhỏ khiến mỗi nơi trở nên gần gũi và đáng nhớ.

Khi trở về, tôi nhận ra rằng một ngày tốt đẹp không nhất thiết phải có điều gì thật đặc biệt. Đôi khi, chỉ cần dành thời gian quan sát, lắng nghe và nói lời cảm ơn đúng lúc, chúng ta đã có thêm nhiều niềm vui. Tôi cất cuốn sách lên bàn, chuẩn bị bữa trưa đơn giản và hẹn mình chiều nay sẽ gọi điện hỏi thăm một người bạn cũ. Cuộc trò chuyện ấy chắc chắn sẽ làm ngày hôm nay thêm ý nghĩa."""

CHECKLIST = """# CP0.3B-5 — Human listening checklist

Compare against the verified B-4 reference. All excerpts come from final WAV.

SPEAKER
- [ ] beginning same speaker
- [ ] middle same speaker
- [ ] end same speaker
- [ ] no voice switch

CONTENT
- [ ] no missing sentence
- [ ] no repeated sentence
- [ ] pronunciation acceptable

QUALITY
- [ ] natural voice
- [ ] pacing acceptable
- [ ] punctuation acceptable
- [ ] no robotic artifact
- [ ] no clipping
- [ ] no click/pop
"""


def main():
    sys.stdout.reconfigure(line_buffering=True)
    evidence_path = ROOT / "reports/cp03b5_long_form_smoke.json"
    listening = ROOT / "reports/cp03b5_listening"
    listening.mkdir(exist_ok=True)
    # Guard against accidentally rerunning successful expensive inference.
    if evidence_path.exists() and json.loads(evidence_path.read_text(encoding="utf-8")).get("status") == "PASS_WITH_LISTENING_REQUIRED":
        raise RuntimeError("Successful smoke already exists; do not regenerate")
    evidence = {"status": "RUNNING", "words": len(TEXT.split()), "characters": len(TEXT),
                "transport": "FastAPI TestClient / real ASGI lifespan and routes",
                "provider_instances": 0, "profile_creations": 0,
                "generation_order": [], "merge_order": [], "profile_ids_used": [],
                "reference": "prototype/voices/e2_test/reference.wav"}
    assert 300 <= evidence["words"] <= 500
    expected = build_chunks(TEXT)
    evidence["chunks"] = len(expected)
    print(json.dumps({k: evidence[k] for k in ("words", "characters", "chunks")}))
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
        def create(*args, **kwargs):
            evidence["profile_creations"] += 1
            return create_profile(*args, **kwargs)
        def clone(**kwargs):
            seen_texts.append(kwargs["text"])
            evidence["generation_order"].append(int(Path(kwargs["output_path"]).stem.split("_")[-1]))
            evidence["profile_ids_used"].append(kwargs["profile"].profile_id)
            object_ids.append(id(kwargs["profile"]))
            model_ids.append(id(provider._model))
            result = synthesize(**kwargs)
            print(f"chunk_finished count={len(seen_texts)} status={result.status} seconds={result.gen_time:.3f}")
            assert result.status == "PASS", "CUDA chunk failed; stop without retry"
            assert provider._load_count == 1 and id(provider._model) == model_ids[0]
            return result
        provider.create_voice_profile = create
        provider.synthesize_cloned = clone
        return service

    def merge(paths, *args, **kwargs):
        evidence["merge_order"] = [int(Path(p).stem.split("_")[-1]) for p in paths]
        assert evidence["merge_order"] == list(range(len(expected)))
        return original_merge(paths, *args, **kwargs)

    app = create_app(provider_service_factory=factory)
    try:
        with patch.object(core, "merge_segments", merge), TestClient(app, base_url="http://127.0.0.1") as client:
            assert not provider.is_loaded()
            ref = ROOT / evidence["reference"]
            assert ref.read_bytes() == (ROOT / "reports/cp03b4_listening/reference.wav").read_bytes()
            evidence["reference_sha256"] = hashlib.sha256(ref.read_bytes()).hexdigest()
            response = client.post("/api/voices/profiles", files={"file": ("reference.wav", ref.read_bytes(), "audio/wav")},
                                   data={"reference_transcript": (ROOT / "prototype/voices/e2_test/transcript.txt").read_text(encoding="utf-8"),
                                         "name": "B5 verified reference"})
            assert response.status_code == 200, f"Profile API status {response.status_code}"
            pid = response.json()["data"]["profile_id"]
            prepared = evidence["profile_creations"]
            start = time.perf_counter()
            response = client.post("/api/tts/long-form", json={"text": TEXT, "language": "vi", "profile_id": pid, "speed": 1.0, "format": "wav"})
            evidence["submission_seconds"] = time.perf_counter() - start
            assert response.status_code == 202
            job_id = response.json()["job_id"]
            evidence["job_id"] = job_id
            evidence["profile_id"] = pid
            evidence_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            progress = []
            while True:
                status = client.get(f"/api/tts/long-form/{job_id}").json()
                progress.append(status["progress_percent"])
                if status["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
                    break
                if time.perf_counter() - start > 3600:
                    client.delete(f"/api/tts/long-form/{job_id}")
                    raise RuntimeError("Smoke timeout; cancellation requested")
                time.sleep(1)
            evidence["total_seconds"] = time.perf_counter() - start
            evidence["job_status"] = status["status"]
            assert status["status"] == "COMPLETED", "Long-form job failed; stop"
            evidence["model_load_count"] = provider._load_count
            evidence["profile_creation_during_job"] = evidence["profile_creations"] - prepared
            evidence["unique_profile_ids_used"] = len(set(evidence["profile_ids_used"]))
            evidence["same_profile_object"] = len(set(object_ids)) == 1
            evidence["same_model_object"] = len(set(model_ids)) == 1
            evidence["progress_monotonic"] = progress == sorted(progress)
            assert seen_texts == [c.text for c in expected]
            assert "".join(TEXT.split()) == "".join("".join(t.split()) for t in seen_texts)
            evidence.update(missing_chunks=0, duplicate_chunks=0, order_violations=0, failed_chunks=0,
                            source_content_preserved=True)
            assert evidence["provider_instances"] == evidence["model_load_count"] == evidence["unique_profile_ids_used"] == 1
            assert evidence["profile_creation_during_job"] == 0
            assert evidence["same_model_object"] and evidence["same_profile_object"] and evidence["progress_monotonic"]
            result = client.get(status["audio_url"])
            assert result.status_code == 200
            final = listening / "long_form.wav"
            final.write_bytes(result.content)
            evidence["audio"] = validate_wav(final)
            evidence["rtf"] = evidence["total_seconds"] / evidence["audio"]["duration"]
            evidence["service_diagnostics"] = app.state.long_form_service.diagnostics(job_id)
            audio, rate = sf.read(final, dtype="int16")
            length = min(12 * rate, len(audio))
            offsets = {"beginning": 0, "middle": (len(audio) - length) // 2, "end": len(audio) - length}
            evidence["extracts"] = {}
            for name, offset in offsets.items():
                path = listening / f"{name}.wav"
                sf.write(path, audio[offset:offset + length], rate, subtype="PCM_16")
                extracted, _ = sf.read(path, dtype="int16")
                assert np.array_equal(extracted, audio[offset:offset + length])
                evidence["extracts"][name] = {"start_seconds": offset / rate, "duration": length / rate,
                                             "exact_final_samples": True}
            evidence["status"] = "PASS_WITH_LISTENING_REQUIRED"
            print(f"smoke_complete seconds={evidence['total_seconds']:.3f} duration={evidence['audio']['duration']:.3f} rtf={evidence['rtf']:.3f}")
    except Exception as exc:
        evidence["status"] = "FAILED"
        evidence["failure_type"] = type(exc).__name__
        raise
    finally:
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
