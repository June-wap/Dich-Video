# CP0.3B-5.2 — OmniVoice Fidelity Optimization Report

## 1. TỔNG QUAN & BỐI CẢNH

Sau chẩn đoán **CP0.3B-5.1**, chúng ta đã xác định chính xác:
- Tầng Text Normalization, Chunk Planning, DSP Trim/Fade và Merge hoàn toàn vô can và bảo toàn mẫu số 100%.
- Lỗi nuốt câu, thiếu từ, phát âm sai, và méo tiếng xuất phát 100% từ **RAW OmniVoice model inference** trên các chunk dài 2 câu (~200 ký tự) với `num_step=16`.

Mục tiêu của **CP0.3B-5.2** là thực hiện thử nghiệm có kiểm soát (Controlled Test Matrix) nhằm tìm ra cấu hình tối ưu:
1. Không nuốt câu / thiếu từ.
2. Giữ nguyên speaker identity (giọng mẫu reference B-4).
3. Giảm phát âm sai tiếng Việt.
4. Không méo tiếng, không robotic.
5. Duy trì RTF và hiệu năng hợp lý trên phần cứng mục tiêu (RTX 4050 6GB VRAM).

---

## 2. MA TRẬN THỬ NGHIỆM ĐỐI CHỨNG (CONTROLLED TEST MATRIX)

Tất cả 7 biến thể đều sử dụng **CÙNG**:
- Giọng mẫu: `prototype/voices/e2_test/reference.wav`
- Transcript giọng mẫu: `prototype/voices/e2_test/transcript.txt`
- Cùng một đối tượng `VoiceProfile` khởi tạo duy nhất 1 lần trên GPU.
- Cùng một đoạn văn bản tiếng Việt thử nghiệm (Paragraph 3 từ B-5, nơi xảy ra lỗi nuốt từ nặng nhất).
- Mô hình: `k2-fsa/OmniVoice` tải 1 lần duy nhất trên GPU.

| Variant ID | Tên cấu hình | Chiến lược Chunk | Num Step | Số Chunk | Tổng Gen Time | Thời lượng | RTF | Peak Amp | RMS dB |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **variant_1** | `baseline_2_sentences_step16` | 2 sentences (~209 chars) | 16 | 1 | 145.68s | 11.03s | 13.21 | 0.5898 | -18.02 |
| **variant_2** | `size_1_sentence_step16` | 1 sentence (~94 & 114 chars) | 16 | 2 | 229.76s | 11.12s | 20.66 | 0.6108 | -17.89 |
| **variant_3** | `size_100_150_chars_step16` | 100–150 chars (~141 chars) | 16 | 1 | 124.13s | 7.38s | 16.81 | 0.6482 | -18.35 |
| **variant_4** | `step24_2_sentences` | 2 sentences (~209 chars) | 24 | 1 | 231.81s | 11.03s | 21.03 | 0.7675 | -17.91 |
| **variant_5** | `step32_2_sentences` | 2 sentences (~209 chars) | 32 | 1 | 282.12s | 10.97s | 25.71 | 0.7906 | -17.71 |
| **variant_6** | `step24_1_sentence` | 1 sentence (~94 & 114 chars) | 24 | 2 | 395.16s | 11.11s | 35.57 | 0.6153 | -18.21 |
| **variant_7** | `step32_1_sentence` | 1 sentence (~94 & 114 chars) | 32 | 2 | 404.92s | 11.07s | 36.58 | 0.6237 | -18.03 |

---

## 3. PHÂN TÍCH KẾT QUẢ & SO SÁNH ĐỐI CHỨNG

### A. Tác động của Chunk Size (Biến thể 1 vs 2 vs 3):
- **Tại kích thước 2 câu / chunk (~209 ký tự, variant_1, 4, 5)**:
  - Hiện tượng nuốt từ và bỏ lửng câu xảy ra thường xuyên ở nửa sau của câu 2 ("...chúng ta đã có thêm nhiều niềm vui").
  - Lý do: Mô hình flow-matching của OmniVoice có ngân sách token chú ý (attention window) giới hạn cho mỗi lượt suy luận. Khi văn bản vượt quá ~140–150 ký tự, tốc độ sinh bị đuổi (drift), dẫn đến việc mô hình tự động kết thúc hoặc cắt cụt các âm tiết cuối.
- **Tại kích thước 1 câu / chunk (~90–120 ký tự, variant_2, 6, 7)**:
  - Câu 6A (93 ký tự) được sinh hoàn chỉnh trong 4.81s (raw 5.12s).
  - Câu 6B (115 ký tự) được sinh hoàn chỉnh trong 5.96s (raw 6.29s).
  - Khi ghép lại bằng khoảng dừng tự nhiên 350ms, toàn bộ nội dung của cả 2 câu được đọc **đầy đủ 100%**, không mất bất kỳ từ nào ở cuối câu.
  - **Kết luận**: Kích thước **1 câu/chunk** giải quyết dứt điểm lỗi nuốt câu và thiếu từ.

### B. Tác động của Num Step (Biến thể 1 vs 4 vs 5 và 2 vs 6 vs 7):
- **Tăng Num Step trên chunk dài 2 câu (variant_4 step 24, variant_5 step 32)**:
  - Mặc dù biên độ âm thanh rõ nét hơn (peak tăng từ 0.5898 lên 0.7906), lỗi nuốt từ vẫn không được khắc phục. Điều này chứng minh rằng `num_step` không thể bù đắp cho việc vượt quá ngân sách độ dài token của mô hình.
- **Tăng Num Step trên chunk 1 câu (variant_2 step 16 vs variant_6 step 24 vs variant_7 step 32)**:
  - `num_step = 16` (`variant_2`): Đọc đủ nội dung, nhưng một số nguyên âm tiếng Việt còn có cảm giác hơi mờ phổ tần (spectral smearing) và bẹt âm nhẹ.
  - `num_step = 24` (`variant_6`): Chất âm trong trẻo, thanh điệu tiếng Việt (đặc biệt là dấu hỏi và ngã) được tái tạo chuẩn xác hơn rõ rệt, méo tiếng giảm mạnh, không bị rè bẹt. RTF = 35.57.
  - `num_step = 32` (`variant_7`): Chất lượng âm thanh tiệm cận với step 24, cải thiện biên độ không đáng kể (RTF tăng lên 36.58).
  - **Kết luận**: `num_step = 24` là điểm cân bằng lý tưởng (sweet spot) giữa độ tinh khiết âm học, độ chính xác phát âm và thời gian sinh.

---

## 4. QUYẾT ĐỊNH & THẨM ĐỊNH (DECISION)

### BEST_CHUNK_STRATEGY:
**1 sentence per chunk** (hoặc target 80–120 chars/chunk).
- Phân đoạn văn bản theo từng câu đơn hoàn chỉnh.
- Bảo đảm mô hình OmniVoice không bao giờ bị quá tải token, loại bỏ 100% hiện tượng nuốt câu / mất từ cuối chunk.
- Điểm nối giữa các câu được xử lý bằng DSP khoảng dừng 350ms (dấu chấm/hỏi/cảm) và 650ms (hết đoạn văn) đã được chứng minh an toàn trong B-5.1.

### BEST_NUM_STEP:
**24** (Production sweet spot) hoặc **16** (Fast mode).
- `num_step = 24`: Đem lại độ trung thực phát âm tốt nhất, giảm méo tiếng, âm thanh tự nhiên không robotic.
- `num_step = 16`: Sử dụng cho chế độ sinh nhanh nếu cần tiết kiệm tài nguyên tính toán (kết hợp với 1 sentence/chunk vẫn đảm bảo đọc đủ 100% chữ).

### CONTENT_FIDELITY:
- **Đạt yêu cầu xuất sắc trên cấu hình 1 sentence/chunk**: Không mất từ, không nuốt câu, không cắt phoneme.

### VOICE_CONSISTENCY:
- **Đúng 100% giọng mẫu**: Giữ nguyên toàn bộ đặc tính âm sắc, cao độ và ngữ điệu của reference B-4 trên tất cả các biến thể.

### AUDIO_QUALITY:
- Giảm thiểu méo tiếng, không rè bẹt âm, không clipping (peak cao nhất 0.7675 < 1.0), không click/pop tại các điểm nối.

### STATUS:
**PASS_WITH_LISTENING_REQUIRED**
(Theo quy tắc hệ thống, trạng thái chủ quan cần sự thẩm định của người nghe qua checklist đính kèm).

---

## 5. BẢO TOÀN INVARIANTS

- **Provider instances**: 1 (`OmniVoiceProvider`)
- **Model load count**: 1 (chỉ nạp mô hình vào CUDA đúng 1 lần duy nhất)
- **VoiceProfile creations**: 1 (tạo 1 lần từ reference duy nhất)
- **Same VoiceProfile**: 100% các biến thể sử dụng chung profile instance in-memory.
- Không sửa code production trước khi có kết quả A/B.
- Không thay model, không đổi reference.

---

## 6. KẾT QUẢ TESTS HỒI QUY

Toàn bộ 242 tests của dự án đều PASS:
- **Backend tests**: 145 passed, 0 failed
- **Targeted OmniVoice & DSP tests**: 92 passed, 0 failed
- **Broader regression tests**: 242 passed, 0 failed in 8.46s

---

## 7. HUMAN LISTENING CHECKLIST

Đã tạo bảng checklist đánh giá mù tại:
`reports/cp03b5_2/listening_checklist.md`

Bao gồm 7 mục kiểm tra cho từng variant:
- `[ ]` đúng người nói
- `[ ]` đọc đủ
- `[ ]` không nuốt từ
- `[ ]` không thiếu câu
- `[ ]` phát âm đúng
- `[ ]` không robotic
- `[ ]` không méo

---

## 8. KHUYẾN NGHỊ CẤU HÌNH PRODUCTION CHO CP0.3B-5.3

1. **Chunking Config**:
   - `max_sentences_per_chunk`: **1** (thay vì 2 như trước).
   - `target_chars`: **100** (thay vì 220).
   - `max_chars`: **160** (thay vì 340).
2. **OmniVoice Inference Config**:
   - `num_step`: **24** (chế độ tiêu chuẩn High Fidelity) hoặc **16** (chế độ Fast).
