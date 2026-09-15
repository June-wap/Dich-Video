"""Text utilities for the prototype."""


# Test sentences for each supported language
TEST_SENTENCES = {
    "vi": "Xin chào, đây là chương trình thử nghiệm chuyển văn bản thành giọng nói.",
    "en": "Hello, this is a text to speech test for the English language.",
    "zh": "你好，这是一个中文语音合成测试。",
    "ja": "こんにちは、これは日本語の音声合成テストです。",
    "es": "Hola, esta es una prueba de síntesis de voz en español.",
    "pt": "Olá, este é um teste de síntese de voz em português.",
    "it": "Ciao, questo è un test di sintesi vocale in italiano.",
    "fr": "Bonjour, ceci est un test de synthèse vocale en français.",
    "hi": "नमस्ते, यह हिन्दी भाषा में वाक् संश्लेषण का परीक्षण है।",
}

# Vietnamese special test cases
VI_TEST_CASES = {
    "normal": "Xin chào, đây là chương trình thử nghiệm chuyển văn bản thành giọng nói.",
    "numbers": "Hôm nay tôi có 125 sản phẩm.",
    "money": "Tổng giá trị đơn hàng là 1.250.000 đồng.",
    "date": "Hôm nay là ngày 12 tháng 9 năm 2026.",
    "percentage": "Doanh thu tăng 15,5 phần trăm.",
    "phone": "Số điện thoại của tôi là 0901234567.",
}

# Conversation test script
CONVERSATION_TEST = [
    {"speaker": "A", "voice_label": "female", "text": "Xin chào, bạn có khỏe không?"},
    {"speaker": "B", "voice_label": "male", "text": "Chào bạn, tôi khỏe. Cảm ơn bạn."},
    {"speaker": "A", "voice_label": "female", "text": "Hôm nay thời tiết đẹp quá nhỉ?"},
    {"speaker": "B", "voice_label": "male", "text": "Đúng rồi, chúng ta đi dạo công viên đi."},
]

# Compatibility export: display metadata has one canonical source.
from core.languages import LANGUAGE_NAMES
