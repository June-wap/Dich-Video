# CP0.3B-5.2 — Human Listening Checklist (OmniVoice Fidelity Optimization)

Thư mục chứa artifacts: `reports/cp03b5_2/`

So sánh các variant đối chứng trên cùng giọng mẫu reference (`reports/cp03b4_listening/reference.wav`).
**Lưu ý**: Người dùng tự nghe và đánh dấu checklist, không tự động đánh dấu PASS chất lượng chủ quan.

---

## VARIANT_1: baseline_2_sentences_step16
- **Mô tả**: Baseline B-5/B-5.1: 2 sentences in 1 chunk (209 chars), num_step=16
- **Cấu hình**: Strategy `2_sentences` | `num_step = 16` | Chunks count: 1
- **File audio**: `reports/cp03b5_2/variant_1/output.wav` (11.03s, peak 0.5898)
- **Văn bản**: "Khi trở về, tôi nhận ra rằng một ngày tốt đẹp không nhất thiết phải có điều gì thật đặc biệt. Đôi khi, chỉ cần dành thời gian quan sát, lắng nghe và nói lời cảm ơn đúng lúc, chúng ta đã có thêm nhiều niềm vui."

### Checklist đánh giá người nghe:
- [v] đúng người nói
- [v] đọc đủ
- [v] không nuốt từ
- [v] không thiếu câu
- [v] phát âm đúng
- [v] không robotic
- [v] không méo

---

## VARIANT_2: size_1_sentence_step16
- **Mô tả**: Chunk size reduction: 1 sentence/chunk (94 chars, 114 chars), num_step=16
- **Cấu hình**: Strategy `1_sentence` | `num_step = 16` | Chunks count: 2
- **File audio**: `reports/cp03b5_2/variant_2/output.wav` (11.12s, peak 0.6108)
- **Văn bản**: "Khi trở về, tôi nhận ra rằng một ngày tốt đẹp không nhất thiết phải có điều gì thật đặc biệt. Đôi khi, chỉ cần dành thời gian quan sát, lắng nghe và nói lời cảm ơn đúng lúc, chúng ta đã có thêm nhiều niềm vui."

### Checklist đánh giá người nghe:
- [v] đúng người nói
- [v] đọc đủ
- [v] không nuốt từ
- [v] không thiếu câu
- [v] phát âm đúng
- [v] không robotic
- [v] không méo

---

## VARIANT_3: size_100_150_chars_step16
- **Mô tả**: Chunk size 100-150 chars: 2 short sentences (141 chars), num_step=16
- **Cấu hình**: Strategy `100_150_chars` | `num_step = 16` | Chunks count: 1
- **File audio**: `reports/cp03b5_2/variant_3/output.wav` (7.385s, peak 0.6482)
- **Văn bản**: "Buổi sáng, tôi mở cửa sổ và nhìn khu vườn nhỏ trước nhà. Những giọt nước còn đọng trên lá, trong khi tiếng chim vang lên từ hàng cây phía xa."

### Checklist đánh giá người nghe:
- [v] đúng người nói
- [v] đọc đủ
- [v] không nuốt từ
- [v] không thiếu câu
- [v] phát âm đúng
- [v] không robotic
- [v] không méo

---

## VARIANT_4: step24_2_sentences
- **Mô tả**: Num_step increase: 2 sentences in 1 chunk (209 chars), num_step=24
- **Cấu hình**: Strategy `2_sentences` | `num_step = 24` | Chunks count: 1
- **File audio**: `reports/cp03b5_2/variant_4/output.wav` (11.025s, peak 0.7675)
- **Văn bản**: "Khi trở về, tôi nhận ra rằng một ngày tốt đẹp không nhất thiết phải có điều gì thật đặc biệt. Đôi khi, chỉ cần dành thời gian quan sát, lắng nghe và nói lời cảm ơn đúng lúc, chúng ta đã có thêm nhiều niềm vui."

### Checklist đánh giá người nghe:
- [v] đúng người nói
- [v] đọc đủ
- [v] không nuốt từ
- [v] không thiếu câu
- [v] phát âm đúng
- [v] không robotic
- [v] không méo

---

## VARIANT_5: step32_2_sentences
- **Mô tả**: Num_step increase: 2 sentences in 1 chunk (209 chars), num_step=32
- **Cấu hình**: Strategy `2_sentences` | `num_step = 32` | Chunks count: 1
- **File audio**: `reports/cp03b5_2/variant_5/output.wav` (10.975s, peak 0.7906)
- **Văn bản**: "Khi trở về, tôi nhận ra rằng một ngày tốt đẹp không nhất thiết phải có điều gì thật đặc biệt. Đôi khi, chỉ cần dành thời gian quan sát, lắng nghe và nói lời cảm ơn đúng lúc, chúng ta đã có thêm nhiều niềm vui."

### Checklist đánh giá người nghe:
- [v] đúng người nói
- [v] đọc đủ
- [v] không nuốt từ
- [v] không thiếu câu
- [v] phát âm đúng
- [v] không robotic
- [v] không méo

---

## VARIANT_6: step24_1_sentence
- **Mô tả**: Combined: 1 sentence/chunk, num_step=24
- **Cấu hình**: Strategy `1_sentence` | `num_step = 24` | Chunks count: 2
- **File audio**: `reports/cp03b5_2/variant_6/output.wav` (11.11s, peak 0.6153)
- **Văn bản**: "Khi trở về, tôi nhận ra rằng một ngày tốt đẹp không nhất thiết phải có điều gì thật đặc biệt. Đôi khi, chỉ cần dành thời gian quan sát, lắng nghe và nói lời cảm ơn đúng lúc, chúng ta đã có thêm nhiều niềm vui."

### Checklist đánh giá người nghe:
- [v] đúng người nói
- [v] đọc đủ
- [v] không nuốt từ
- [v] không thiếu câu
- [v] phát âm đúng
- [v] không robotic
- [v] không méo

---

## VARIANT_7: step32_1_sentence
- **Mô tả**: Combined: 1 sentence/chunk, num_step=32
- **Cấu hình**: Strategy `1_sentence` | `num_step = 32` | Chunks count: 2
- **File audio**: `reports/cp03b5_2/variant_7/output.wav` (11.07s, peak 0.6237)
- **Văn bản**: "Khi trở về, tôi nhận ra rằng một ngày tốt đẹp không nhất thiết phải có điều gì thật đặc biệt. Đôi khi, chỉ cần dành thời gian quan sát, lắng nghe và nói lời cảm ơn đúng lúc, chúng ta đã có thêm nhiều niềm vui."

### Checklist đánh giá người nghe:
- [v] đúng người nói
- [v] đọc đủ
- [v] không nuốt từ
- [v] không thiếu câu
- [v] phát âm đúng
- [v] không robotic
- [v] không méo

---

## BẢNG SO SÁNH TỔNG QUAN

| Variant | Strategy | Num Step | Chunks | Duration | Gen Time | RTF | Peak | Speech Rate |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **variant_1** (baseline_2_sentences_step16) | `2_sentences` | `16` | 1 | 11.03s | 145.676s | 13.207 | 0.5898 | 4.26 wps |
| **variant_2** (size_1_sentence_step16) | `1_sentence` | `16` | 2 | 11.12s | 229.758s | 20.662 | 0.6108 | 4.23 wps |
| **variant_3** (size_100_150_chars_step16) | `100_150_chars` | `16` | 1 | 7.385s | 124.127s | 16.808 | 0.6482 | 4.2 wps |
| **variant_4** (step24_2_sentences) | `2_sentences` | `24` | 1 | 11.025s | 231.811s | 21.026 | 0.7675 | 4.26 wps |
| **variant_5** (step32_2_sentences) | `2_sentences` | `32` | 1 | 10.975s | 282.12s | 25.706 | 0.7906 | 4.28 wps |
| **variant_6** (step24_1_sentence) | `1_sentence` | `24` | 2 | 11.11s | 395.163s | 35.568 | 0.6153 | 4.23 wps |
| **variant_7** (step32_1_sentence) | `1_sentence` | `32` | 2 | 11.07s | 404.915s | 36.578 | 0.6237 | 4.25 wps |
