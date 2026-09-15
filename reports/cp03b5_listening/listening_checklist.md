# CP0.3B-5 — Human Listening Checklist

Compare against the verified B-4 reference audio (`reports/cp03b4_listening/reference.wav`).
Excerpts (`beginning.wav`, `middle.wav`, `end.wav`) are 12-second PCM slices copied directly from `long_form.wav` without regeneration.

SPEAKER
[x] same speaker at beginning (BEGINNING: cùng người nói)
[x] same speaker in middle (MIDDLE: cùng người nói)
[x] same speaker at end (END: cùng người nói)
[x] no voice switch

CONTENT
[ ] no missing sentence (Nuốt câu: CÓ)
[x] no repeated sentence (Lặp câu: KHÔNG)
[ ] no obvious word loss (Thiếu từ: CÓ)
[ ] pronunciation acceptable (Phát âm sai: CÓ)

QUALITY
[ ] natural voice (Méo tiếng: CÓ)
[x] normal pacing
[x] punctuation sounds correct
[x] paragraph pauses acceptable (Ngắt câu bất thường: KHÔNG)
[x] no severe robotic artifact (Robotic: KHÔNG)
[x] no clipping
[x] no click/pop (Click/pop: KHÔNG)

---
### Human Listening Evaluation Summary:
- **Speaker Consistency**: PASS (Đúng giọng reference, cùng người nói xuyên suốt beginning, middle, end, không bị đổi giọng).
- **Acoustic / Model Synthesis Limitations**:
  - Nuốt câu: Có (OmniVoice model bỏ sót câu trong quá trình sinh âm thanh ở một số chunk).
  - Thiếu từ: Có (hiện tượng nuốt/mất chữ ở một số vị trí).
  - Phát âm sai: Có (lỗi phát âm từ ngữ tiếng Việt của mô hình).
  - Méo tiếng: Có (hiện tượng biến dạng âm thanh / méo tiếng cục bộ).
  - Lặp câu: Không.
  - Robot: Không.
  - Ngắt câu bất thường: Không.
  - Click/pop: Không.
