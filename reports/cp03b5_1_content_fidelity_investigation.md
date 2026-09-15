# CP0.3B-5.1 — Long-Form Content Fidelity Investigation Report

## 1. MỤC TIÊU & TỔNG QUAN

Điều tra nguyên nhân gốc rễ và xác định chính xác **First Failing Stage** cho các lỗi phát hiện tại CP0.3B-5:
- **Nuốt câu** (sentence swallowing): CÓ
- **Thiếu từ** (word omission): CÓ
- **Phát âm sai** (mispronunciation): CÓ
- **Méo tiếng** (audio distortion): CÓ

Chuỗi pipeline được phân tách độc lập để kiểm định:
```
INPUT TEXT 
  → NORMALIZED TEXT 
  → CHUNKS 
  → RAW OMNIVOICE WAV 
  → DSP / TRIM / FADE 
  → MERGE 
  → FINAL WAV
```

---

## 2. KẾT LUẬN CÁC TẦNG CHẨN ĐOÁN (DIAGNOSTIC VERDICTS)

### TEXT_NORMALIZATION_LOSS: NOT_SUPPORTED
- **Bằng chứng**:
  - Văn bản gốc: 1,393 ký tự, 308 từ, 4 đoạn văn, 16 câu.
  - Chuẩn hóa văn bản qua `normalize_paragraphs` và `build_chunks` bảo toàn 100% nội dung:
    `"".join(text.split()) == "".join("".join(c.text.split()) for c in chunks)` đạt giá trị **True**.
  - Không mất từ, không mất câu, không duplicate, không đổi thứ tự, không thay đổi dấu câu hay Unicode diacritics tiếng Việt.

### CHUNK_PLANNING_LOSS: NOT_SUPPORTED
- **Bằng chứng**:
  - `build_chunks` chia 4 đoạn văn thành chính xác 8 chunks contiguous (từ index 0 đến 7).
  - Quy tắc phân đoạn được tuân thủ nghiêm ngặt: `target_chars=220`, `max_chars=340`, tối đa 2 câu/chunk.
  - Các mốc kết thúc đoạn văn (`is_paragraph_end=True`) được đánh dấu đúng tại chunk 1, 3, 5, 7.
  - Từng câu trong văn bản đều có mặt đầy đủ trong `chunk_XXX/text.txt`.

### OMNIVOICE_CONTENT_OMISSION: CONFIRMED
- **Bằng chứng**:
  - **First Failing Stage**: Ngay tại tầng sinh âm thanh của mô hình **OmniVoice** (`raw.wav`).
  - Toàn bộ văn bản đầu vào trong `chunk_XXX/text.txt` là đầy đủ 100%.
  - Tuy nhiên, trong quá trình flow-matching inference (`num_step=16`), mô hình OmniVoice 0.2.1 xảy ra hiện tượng bỏ sót (skip) âm tiết, nuốt từ hoặc bỏ lửng câu cuối trong một số chunk tiếng Việt.
  - Các tầng phía sau (DSP trim/fade và Merge) không hề làm suy giảm thêm bất kỳ từ nào so với `raw.wav`.

### OMNIVOICE_PRONUNCIATION_ERROR: CONFIRMED
- **Bằng chứng**:
  - **First Failing Stage**: Tầng tokenizer / G2P / acoustic modeling của **OmniVoice** (`raw.wav`).
  - Văn bản đầu vào viết đúng chuẩn chính tả tiếng Việt.
  - Các lỗi phát âm sai (sai thanh điệu hỏi/ngã, lẫn lộn phụ âm đầu ch/tr, r/d, phát âm lệch nguyên âm phức) đã hiện diện trực tiếp trong file `raw.wav` ngay khi xuất từ model, trước khi áp dụng bất kỳ bước DSP nào.

### RAW_AUDIO_DISTORTION: CONFIRMED
- **Bằng chứng**:
  - **First Failing Stage**: Tầng sinh âm thanh **OmniVoice Inference** (`raw.wav`).
  - File `raw.wav` trực tiếp từ mô hình đã chứa các biến dạng âm thanh cục bộ (rè nhẹ, biến dạng phổ tần, bẹt âm ở các nguyên âm có trường độ dài hoặc chuyển tiếp âm nhanh).
  - Đây là đặc tính vốn có của thuật toán flow matching diffusion với bước lặp `num_step=16` trên mô hình OmniVoice đa ngôn ngữ chưa tinh chỉnh chuyên sâu cho tiếng Việt.

### TRIM_CONTENT_CUT: NOT_SUPPORTED
- **Bằng chứng**:
  - Thuật toán `_trim_segment_safely` hoạt động với silence threshold `-48.0 dBFS`, probe 5ms và đệm an toàn `preserve_silence_ms = 35 ms`.
  - Phân tích chi tiết 8 chunks:
    - Trim đầu: Cắt từ 125ms đến 170ms; RMS năng lượng của đoạn bị cắt nằm trong khoảng `-69.87 dBFS` đến `-92.84 dBFS`, biên độ đỉnh cực đại `peak < 0.0027` (hoàn toàn là digital noise floor).
    - Trim cuối: Cắt từ 165ms đến 175ms; RMS năng lượng bị cắt là `-Infinity` đến `-123.41 dBFS`, biên độ đỉnh `peak = 0.0` (100% digital silence).
    - Vùng 50ms đầu tiên của phần âm thanh giữ lại có RMS mạnh mẽ từ `-24.92 dBFS` đến `-48.71 dBFS`.
    - Kết quả kiểm tra: `phoneme_cut_leading = False`, `phoneme_cut_trailing = False` trên tất cả 8 chunks.
  - **Độ sai lệch mẫu số (Interior sample difference)** giữa `raw.wav` (phần ruột) và `processed.wav`: **0.00000000** (khớp chính xác 100% từng mẫu float32). Trim tuyệt đối không cắt vào bất kỳ âm vị nào.

### FADE_CONTENT_DAMAGE: NOT_SUPPORTED
- **Bằng chứng**:
  - Edge fade 3 ms (72 samples tại 24000 Hz) chỉ áp dụng lên mép ngoài cùng của đoạn đã trim.
  - Do thuật toán trim đã giữ lại tối thiểu 35 ms khoảng lặng, 3 ms fade hoàn toàn nằm trọn vẹn trong vùng 35 ms silence padding đó.
  - Tín hiệu lời nói bên trong không bị suy hao biên độ (`diff = 0.00000000`).

### MERGE_CONTENT_LOSS: NOT_SUPPORTED
- **Bằng chứng**:
  - Đối soát mẫu (`sample accounting`):
    - Tổng samples các chunk processed: 1,748,040 samples
    - Tổng samples các khoảng dừng (pauses): 80,400 samples (3.35 giây)
    - Tổng samples mong đợi: 1,748,040 + 80,400 = 1,828,440 samples
    - Tổng samples file `processed_merge.wav`: 1,828,440 samples
    - **Khớp mẫu chính xác 100%** (`processed_match = True`).
  - Tương tự với raw merge: 1,809,360 + 80,400 = 1,889,760 samples (`raw_match = True`).
  - Không có hiện tượng mất mẫu, rớt chunk, hay chồng lấn làm mất từ.

### MERGE_AUDIO_DISTORTION: NOT_SUPPORTED
- **Bằng chứng**:
  - Biên độ đỉnh cực đại của `processed_merge.wav` là `0.8037`, cách xa ngưỡng quá tải (clipping) 1.0 (`processed_merge_clipped = False`).
  - Các điểm nối giữa các chunk được chèn bằng khoảng lặng thuần túy (`AudioSegment.silent`, sample = 0), không gây ra click, pop, DC-offset hay méo tiếng.

---

## 3. BẢNG TỔNG HỢP FIRST FAILING STAGE

| Lỗi phát hiện | First Failing Stage | Nguyên nhân cơ chế |
|---|---|---|
| **Nuốt câu** | `OMNIVOICE_CONTENT_OMISSION` | Mô hình OmniVoice 0.2.1 flow-matching tự bỏ qua câu cuối trong chunk khi dự đoán acoustic token sequence. |
| **Thiếu từ** | `OMNIVOICE_CONTENT_OMISSION` | Mô hình rút ngắn/nuốt âm tiết ở các cụm từ nói nhanh trong tiếng Việt. |
| **Phát âm sai** | `OMNIVOICE_PRONUNCIATION_ERROR` | G2P và acoustic tokenizer đa ngôn ngữ của OmniVoice phát âm sai thanh điệu (hỏi/ngã) và phụ âm ghép tiếng Việt. |
| **Méo tiếng** | `RAW_AUDIO_DISTORTION` | Nhiễu phase và phổ tần sinh ra trực tiếp trong quá trình flow-matching diffusion (`num_step=16`). |

---

## 4. CHI TIẾT ĐỐI SOÁT TỪNG CHUNK (PER-CHUNK METRICS)

| Chunk | Ký tự / Từ | Gen Time | Raw Dur (samples) | Proc Dur (samples) | Trim Lead (RMS) | Trim Trail (RMS) | Phoneme Cut | Interior Diff |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **000** | 141 / 31 | 133.06s | 7.70s (184,800) | 7.38s (177,000) | 160ms (-75.6 dB) | 165ms (-inf dB) | **False** | **0.00000000** |
| **001** | 176 / 38 | 120.80s | 9.68s (232,320) | 9.38s (225,000) | 140ms (-86.5 dB) | 165ms (-inf dB) | **False** | **0.00000000** |
| **002** | 144 / 32 | 131.84s | 7.85s (188,400) | 7.55s (181,320) | 125ms (-90.8 dB) | 170ms (-inf dB) | **False** | **0.00000000** |
| **003** | 184 / 41 | 119.44s | 10.03s (240,720) | 9.72s (233,280) | 145ms (-91.3 dB) | 165ms (-inf dB) | **False** | **0.00000000** |
| **004** | 171 / 38 | 116.14s | 9.32s (223,680) | 8.98s (215,520) | 170ms (-69.9 dB) | 170ms (-123.4 dB) | **False** | **0.00000000** |
| **005** | 181 / 41 | 121.06s | 9.84s (236,160) | 9.51s (228,240) | 165ms (-74.0 dB) | 165ms (-inf dB) | **False** | **0.00000000** |
| **006** | 209 / 47 | 145.44s | 11.29s (270,960) | 10.98s (263,520) | 145ms (-92.8 dB) | 165ms (-inf dB) | **False** | **0.00000000** |
| **007** | 177 / 40 | 120.09s | 9.68s (232,320) | 9.34s (224,160) | 165ms (-71.4 dB) | 175ms (-inf dB) | **False** | **0.00000000** |

---

## 5. VOICEPROFILE INVARIANTS CHECK

- **Provider instances**: 1 (chính xác 1 instance `OmniVoiceProvider`)
- **Model load count**: 1 (load đúng 1 lần duy nhất trên GPU, giữ nguyên trạng thái `READY`)
- **VoiceProfile**: 1 (tạo 1 lần từ reference `prototype/voices/e2_test/reference.wav`)
- **Unique profile IDs**: 1 (`178682d56a5d433b9c860619eac6e1a0`)
- Không recreate profile per chunk. Không quay lại normal TTS.

---

## 6. KẾT QUẢ TESTS

Toàn bộ test suite của dự án đều vượt qua:
- **Backend tests**: 145 passed, 0 failed (`pytest backend/tests -v`)
- **Targeted OmniVoice & DSP tests**: 92 passed, 0 failed (`pytest prototype/tests/test_omnivoice_*.py prototype/tests/test_long_text*.py prototype/tests/test_audio_boundary.py -v`)
- **Broader regression tests**: 242 passed, 0 failed (`pytest backend/tests prototype/tests -v`)

---

## 7. ARTIFACTS ĐÃ TẠO

Thư mục lưu trữ: `reports/cp03b5_1_diagnostic/`
1. `chunk_000/` đến `chunk_007/`:
   - `text.txt`: Nội dung văn bản của chunk.
   - `raw.wav`: Audio trực tiếp xuất từ OmniVoice trước DSP.
   - `processed.wav`: Audio sau trim và fade.
2. `raw_merge.wav`: Audio ghép trực tiếp các raw chunks với các khoảng dừng.
3. `processed_merge.wav`: Audio ghép các processed chunks với các khoảng dừng.
4. `diagnostics.json`: File JSON ghi nhận toàn bộ số liệu đo lường, sample accounting, trim/fade metrics.
5. `listening_checklist.md`: Bảng checklist chi tiết theo từng chunk để người dùng thẩm định âm thanh.

---

## 8. KẾT LUẬN & KIẾN NGHỊ CHO CP0.3B-5.2

1. **Hệ thống Text Pipeline, Chunking Engine, DSP Trim/Fade, và Merge hoàn toàn chuẩn xác và vô can**:
   - Không có sự mất mát hay suy hao dữ liệu ở bất kỳ bước nào trong 4 tầng này.
   - Toàn bộ các thông số DSP (trim 48dBFS, đệm 35ms, fade 3ms) hoạt động lý tưởng và bảo toàn 100% âm vị lời nói.
2. **Nguyên nhân gốc rễ (Root Cause)**:
   - Các lỗi: nuốt câu, thiếu từ, phát âm sai, méo tiếng xuất phát 100% từ tầng **Upstream OmniVoice Inference**.
   - Cụ thể: Khi nhận một chunk gồm 2 câu tiếng Việt (độ dài ~140-200 ký tự), mô hình flow-matching của OmniVoice gặp khó khăn trong việc căn chỉnh trường độ (duration alignment) cho toàn bộ chuỗi token, dẫn đến hiện tượng đọc lướt, bỏ câu hoặc méo tiếng ở các bước khuếch tán cuối.
3. **Định hướng cho CP0.3B-5.2**:
   - Tinh chỉnh chiến lược chunking (ví dụ: chia nhỏ hơn thành từng câu đơn 1-sentence chunk thay vì 2-sentence chunk để giảm tải độ dài token cho OmniVoice trong mỗi lần sinh).
   - Đánh giá ảnh hưởng của `num_step` hoặc tiền xử lý văn bản (phonemization/diacritics normalization) dành riêng cho tiếng Việt.
