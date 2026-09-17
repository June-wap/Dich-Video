"""POC: đánh giá chất lượng dịch máy MADLAD-400 cho vi -> 8 ngôn ngữ còn lại.

KHÔNG đụng vào backend/production code - đây là script nghiên cứu độc lập,
đúng tinh thần scripts/cp0_benchmark.py đã làm khi đánh giá Piper. Không tự
động ghi đè, không import bất kỳ module nào trong backend/ hay prototype/.

Cách chạy (dùng lại venv chính thức đã có sẵn torch+transformers, chỉ cần
thêm sentencepiece cho tokenizer của MADLAD-400):

    & "D:\\Tool Dich Cho Khach\\external\\OmniVoice\\.venv312\\Scripts\\pip.exe" install sentencepiece
    & "D:\\Tool Dich Cho Khach\\external\\OmniVoice\\.venv312\\Scripts\\python.exe" scripts\\mt_poc_madlad.py

Lần chạy đầu tiên sẽ tải model MADLAD-400 (bản 3B, ~vài GB) từ Hugging Face
qua mạng - cần internet lúc này (khác với backend chính chạy offline).
Nếu máy không đủ VRAM cho GPU, tắt backend trước khi chạy POC này để giải
phóng VRAM, hoặc set biến môi trường MT_POC_FORCE_CPU=1 để ép chạy CPU
(chậm hơn nhưng vẫn ra kết quả để đánh giá CHẤT LƯỢNG DỊCH, vốn không phụ
thuộc CPU/GPU).

Script này KHÔNG tự đánh giá đúng/sai - in ra bản gốc + bản dịch cho từng
ngôn ngữ để người đọc (hoặc dán lại cho Claude) tự đọc và nhận xét chất
lượng, vì đây là văn bản (không phải audio) nên có thể đọc trực tiếp,
không cần công cụ nhận dạng giọng nói nào.
"""
import json
import os
import time
from pathlib import Path

import torch
from transformers import T5ForConditionalGeneration, T5Tokenizer

MODEL_ID = "google/madlad400-3b-mt"

# Mã ngôn ngữ đích -> tên hiển thị. MADLAD-400 dùng token tiền tố "<2xx>"
# (xx là mã ISO) để chọn ngôn ngữ đích, đặt ngay trước văn bản nguồn.
TARGETS = {
    "en": "English",
    "es": "Spanish",
    "pt": "Portuguese",
    "fr": "French",
    "it": "Italian",
    "zh": "Chinese",
    "ja": "Japanese",
    "hi": "Hindi",
}

# Câu mẫu tiếng Việt - cố tình chọn văn phong dịch vụ khách hàng, giống
# ngữ cảnh thực tế "Tool Dich Cho Khach" sẽ dùng, không phải câu demo chung
# chung kiểu "Xin chào thế giới".
SOURCE_TEXTS = [
    "Xin chào, cảm ơn quý khách đã sử dụng dịch vụ của chúng tôi.",
    "Đơn hàng của bạn sẽ được giao trong vòng ba đến năm ngày làm việc.",
    "Vui lòng liên hệ tổng đài nếu quý khách cần hỗ trợ thêm.",
]


def main():
    force_cpu = os.getenv("MT_POC_FORCE_CPU") == "1"
    device = "cpu" if force_cpu else ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== MADLAD-400 Translation POC ===")
    print(f"Device: {device}")
    print("Đang tải model (lần đầu sẽ tải qua mạng, có thể mất vài phút tuỳ tốc độ mạng)...")

    t0 = time.perf_counter()
    tokenizer = T5Tokenizer.from_pretrained(MODEL_ID)
    model = T5ForConditionalGeneration.from_pretrained(MODEL_ID).to(device)
    print(f"Model loaded in {time.perf_counter() - t0:.1f}s")

    results = []
    for lang_code, lang_name in TARGETS.items():
        print("\n" + "=" * 60)
        print(f"Ngôn ngữ đích: {lang_code} ({lang_name})")
        for text in SOURCE_TEXTS:
            prompt = f"<2{lang_code}> {text}"
            input_ids = tokenizer(prompt, return_tensors="pt").input_ids.to(device)

            start = time.perf_counter()
            output_ids = model.generate(input_ids=input_ids, max_new_tokens=128)
            elapsed = time.perf_counter() - start

            translated = tokenizer.decode(output_ids[0], skip_special_tokens=True)

            print(f"  Gốc:  {text}")
            print(f"  Dịch: {translated}")
            print(f"  Thời gian: {elapsed:.2f}s")
            print()

            results.append({
                "language": lang_code,
                "language_name": lang_name,
                "source_vi": text,
                "translated": translated,
                "generation_time_sec": round(elapsed, 3),
            })

    out_path = Path("mt_poc_results.json")
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("HOÀN TẤT")
    print(f"Kết quả đầy đủ đã lưu: {out_path.resolve()}")
    print("Gửi lại nội dung file này (hoặc dán trực tiếp) để đánh giá chất lượng dịch từng ngôn ngữ.")


if __name__ == "__main__":
    main()
