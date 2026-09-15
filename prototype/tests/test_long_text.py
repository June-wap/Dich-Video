from __future__ import annotations

import pytest

from core.long_text import (
    ChunkStatus,
    ChunkingConfig,
    TextChunk,
    build_chunks,
    normalize_paragraphs,
    split_long_sentence,
    split_sentences,
)


# ============================================================
# BASIC STRUCTURE
# ============================================================


def test_chunk_status_values():
    assert ChunkStatus.PENDING.value == "PENDING"
    assert ChunkStatus.GENERATING.value == "GENERATING"
    assert ChunkStatus.COMPLETED.value == "COMPLETED"
    assert ChunkStatus.FAILED.value == "FAILED"
    assert ChunkStatus.CANCELLED.value == "CANCELLED"


def test_text_chunk_defaults():
    chunk = TextChunk(
        index=0,
        text="Xin chào.",
        paragraph_index=0,
        sentence_count=1,
        is_paragraph_end=True,
    )

    assert chunk.status == ChunkStatus.PENDING
    assert chunk.attempts == 0
    assert chunk.error is None


def test_default_chunking_config():
    config = ChunkingConfig()

    assert config.target_chars == 100
    assert config.max_chars == 160
    assert config.max_sentences_per_chunk == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"target_chars": 0},
        {"target_chars": -1},
        {"max_chars": 0},
        {"max_chars": -1},
        {
            "target_chars": 400,
            "max_chars": 300,
        },
        {
            "max_sentences_per_chunk": 0,
        },
    ],
)
def test_invalid_chunking_config(kwargs):
    with pytest.raises(ValueError):
        ChunkingConfig(**kwargs)


# ============================================================
# PARAGRAPHS
# ============================================================


def test_normalize_paragraphs_preserves_boundaries():
    text = """
Đây là đoạn thứ nhất.
Vẫn thuộc đoạn thứ nhất.

Đây là đoạn thứ hai.

Đây là đoạn thứ ba.
""".strip()

    paragraphs = normalize_paragraphs(text)

    assert len(paragraphs) == 3

    assert paragraphs[0] == (
        "Đây là đoạn thứ nhất. "
        "Vẫn thuộc đoạn thứ nhất."
    )

    assert paragraphs[1] == (
        "Đây là đoạn thứ hai."
    )

    assert paragraphs[2] == (
        "Đây là đoạn thứ ba."
    )


def test_normalize_paragraphs_empty_text():
    assert normalize_paragraphs("") == []
    assert normalize_paragraphs("   ") == []


def test_normalize_paragraphs_non_string():
    assert normalize_paragraphs(None) == []


# ============================================================
# SENTENCE SPLITTING
# ============================================================


def test_split_sentences_vietnamese():
    text = (
        "Xin chào. "
        "Bạn có khỏe không? "
        "Hôm nay thật đẹp!"
    )

    sentences = split_sentences(text)

    assert sentences == [
        "Xin chào.",
        "Bạn có khỏe không?",
        "Hôm nay thật đẹp!",
    ]


def test_split_sentences_cjk_punctuation():
    text = "こんにちは。元気ですか？今日は良い日です！"

    sentences = split_sentences(text)

    assert sentences == [
        "こんにちは。",
        "元気ですか？",
        "今日は良い日です！",
    ]


def test_split_sentences_chinese():
    text = "你好。你好吗？今天很好！"

    sentences = split_sentences(text)

    assert sentences == [
        "你好。",
        "你好吗？",
        "今天很好！",
    ]


def test_split_sentences_empty():
    assert split_sentences("") == []
    assert split_sentences("   ") == []


# ============================================================
# LONG SENTENCE FALLBACK
# ============================================================


def test_short_sentence_not_split():
    sentence = "Đây là một câu ngắn."

    parts = split_long_sentence(
        sentence,
        max_chars=100,
    )

    assert parts == [sentence]


def test_long_sentence_prefers_punctuation_boundaries():
    sentence = (
        "Đây là phần thứ nhất, "
        "đây là phần thứ hai, "
        "đây là phần thứ ba, "
        "đây là phần thứ tư."
    )

    parts = split_long_sentence(
        sentence,
        max_chars=45,
    )

    assert len(parts) > 1

    for part in parts:
        assert len(part) <= 45


def test_long_sentence_hard_fallback_never_exceeds_limit():
    sentence = "a" * 1000

    parts = split_long_sentence(
        sentence,
        max_chars=100,
    )

    assert len(parts) == 10

    for part in parts:
        assert len(part) <= 100


# ============================================================
# BUILD CHUNKS
# ============================================================


def test_build_chunks_empty_text():
    assert build_chunks("") == []
    assert build_chunks("   ") == []


def test_build_chunks_single_sentence():
    chunks = build_chunks(
        "Xin chào mọi người."
    )

    assert len(chunks) == 1

    chunk = chunks[0]

    assert chunk.index == 0
    assert chunk.text == "Xin chào mọi người."
    assert chunk.paragraph_index == 0
    assert chunk.sentence_count == 1
    assert chunk.is_paragraph_end is True
    assert chunk.status == ChunkStatus.PENDING


def test_build_chunks_preserves_order():
    text = (
        "Câu thứ nhất. "
        "Câu thứ hai. "
        "Câu thứ ba. "
        "Câu thứ tư."
    )

    config = ChunkingConfig(
        target_chars=500,
        max_chars=500,
        max_sentences_per_chunk=1,
    )

    chunks = build_chunks(
        text,
        config,
    )

    assert [
        chunk.text
        for chunk in chunks
    ] == [
        "Câu thứ nhất.",
        "Câu thứ hai.",
        "Câu thứ ba.",
        "Câu thứ tư.",
    ]

    assert [
        chunk.index
        for chunk in chunks
    ] == [0, 1, 2, 3]


def test_build_chunks_max_two_sentences():
    text = (
        "Câu một. "
        "Câu hai. "
        "Câu ba. "
        "Câu bốn. "
        "Câu năm."
    )

    config = ChunkingConfig(
        target_chars=500,
        max_chars=500,
        max_sentences_per_chunk=2,
    )

    chunks = build_chunks(
        text,
        config,
    )

    assert len(chunks) == 3

    assert chunks[0].sentence_count == 2
    assert chunks[1].sentence_count == 2
    assert chunks[2].sentence_count == 1


def test_build_chunks_respects_hard_max():
    sentence = (
        "Đây là một câu rất dài, "
        "chứa nhiều phần nội dung khác nhau, "
        "được sử dụng để kiểm tra việc chia đoạn, "
        "và phải được chia hợp lý khi vượt giới hạn."
    )

    config = ChunkingConfig(
        target_chars=60,
        max_chars=80,
        max_sentences_per_chunk=2,
    )

    chunks = build_chunks(
        sentence,
        config,
    )

    assert len(chunks) > 1

    for chunk in chunks:
        assert len(chunk.text) <= 80


def test_build_chunks_preserves_paragraph_index():
    text = """
Đoạn một câu một. Đoạn một câu hai.

Đoạn hai câu một. Đoạn hai câu hai.

Đoạn ba câu một.
""".strip()

    chunks = build_chunks(text)

    paragraph_indexes = {
        chunk.paragraph_index
        for chunk in chunks
    }

    assert paragraph_indexes == {
        0,
        1,
        2,
    }


def test_build_chunks_marks_last_chunk_of_each_paragraph():
    text = """
Đoạn một câu một. Đoạn một câu hai. Đoạn một câu ba.

Đoạn hai câu một. Đoạn hai câu hai.
""".strip()

    config = ChunkingConfig(
        target_chars=500,
        max_chars=500,
        max_sentences_per_chunk=2,
    )

    chunks = build_chunks(
        text,
        config,
    )

    paragraph_zero = [
        c
        for c in chunks
        if c.paragraph_index == 0
    ]

    paragraph_one = [
        c
        for c in chunks
        if c.paragraph_index == 1
    ]

    assert (
        paragraph_zero[-1]
        .is_paragraph_end
        is True
    )

    for chunk in paragraph_zero[:-1]:
        assert (
            chunk.is_paragraph_end
            is False
        )

    assert (
        paragraph_one[-1]
        .is_paragraph_end
        is True
    )


# ============================================================
# MULTILINGUAL / UNICODE
# ============================================================


@pytest.mark.parametrize(
    "text",
    [
        "Xin chào. Đây là tiếng Việt.",
        "Hello. This is English.",
        "你好。这是中文。",
        "こんにちは。これは日本語です。",
        "Hola. Esto es español.",
        "Olá. Isto é português.",
        "Ciao. Questo è italiano.",
        "Bonjour. Ceci est français.",
        "नमस्ते। यह हिंदी है।",
    ],
)
def test_build_chunks_unicode_languages(text):
    chunks = build_chunks(text)

    assert len(chunks) >= 1

    reconstructed = " ".join(
        chunk.text
        for chunk in chunks
    )

    assert reconstructed


# ============================================================
# DEFAULT LONG TEXT BEHAVIOR
# ============================================================


def test_realistic_long_vietnamese_text_creates_multiple_chunks():
    text = """
Trong cuộc sống hiện đại, công nghệ đang thay đổi cách con người làm việc,
học tập và giao tiếp với nhau. Những hệ thống trí tuệ nhân tạo ngày càng
được ứng dụng rộng rãi trong nhiều lĩnh vực khác nhau.

Một trong những ứng dụng đáng chú ý là công nghệ chuyển văn bản thành giọng
nói. Thay vì phải thu âm thủ công từng câu, người dùng có thể nhập nội dung
văn bản và để hệ thống tự động tạo ra âm thanh với giọng đọc tự nhiên.

Đối với các nhà sáng tạo nội dung, công nghệ này có thể giúp tiết kiệm rất
nhiều thời gian. Một video dài, một bài thuyết minh hoặc một nội dung đào tạo
có thể được tạo giọng đọc trong thời gian ngắn hơn đáng kể.
""".strip()

    chunks = build_chunks(text)

    assert len(chunks) > 1

    for chunk in chunks:
        assert chunk.text
        assert (
            len(chunk.text)
            <= ChunkingConfig().max_chars
        )


def test_chunk_indexes_are_contiguous():
    text = (
        "Một. Hai. Ba. Bốn. "
        "Năm. Sáu. Bảy. Tám."
    )

    config = ChunkingConfig(
        target_chars=500,
        max_chars=500,
        max_sentences_per_chunk=1,
    )

    chunks = build_chunks(
        text,
        config,
    )

    assert [
        chunk.index
        for chunk in chunks
    ] == list(
        range(len(chunks))
    )