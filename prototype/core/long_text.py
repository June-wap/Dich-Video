"""Long-text chunking primitives for CP0.2D and CP0.3B-5.3."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ChunkStatus(str, Enum):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class TextChunk:
    index: int
    text: str
    paragraph_index: int
    sentence_count: int
    is_paragraph_end: bool
    status: ChunkStatus = ChunkStatus.PENDING
    attempts: int = 0
    error: str | None = None


@dataclass(frozen=True)
class ChunkingConfig:
    target_chars: int = 100
    max_chars: int = 160
    max_sentences_per_chunk: int = 1

    def __post_init__(self) -> None:
        if self.target_chars <= 0:
            raise ValueError("target_chars must be > 0")

        if self.max_chars <= 0:
            raise ValueError("max_chars must be > 0")

        if self.target_chars > self.max_chars:
            raise ValueError(
                "target_chars must be <= max_chars"
            )

        if self.max_sentences_per_chunk <= 0:
            raise ValueError(
                "max_sentences_per_chunk must be > 0"
            )


def normalize_paragraphs(text: str) -> list[str]:
    """Normalize whitespace while preserving paragraph boundaries."""

    if not isinstance(text, str):
        return []

    text = text.strip()

    if not text:
        return []

    raw_paragraphs = re.split(
        r"\n\s*\n+",
        text,
    )

    paragraphs: list[str] = []

    for block in raw_paragraphs:
        lines = [
            re.sub(r"[ \t]+", " ", line).strip()
            for line in block.splitlines()
            if line.strip()
        ]

        paragraph = " ".join(lines).strip()

        if paragraph:
            paragraphs.append(paragraph)

    return paragraphs


def split_sentences(text: str) -> list[str]:
    """Split common sentence endings without language fallback."""

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    ).strip()

    if not text:
        return []

    # Keep decimal numbers, ellipses and closing quotes together. Latin
    # sentence boundaries require whitespace; CJK punctuation does not.
    parts = []
    start = 0
    for match in re.finditer(r'''(?:[.!?…]+["'”’»)]*(?=\s|$)|[。！？]+["'”’»)]*)''', text):
        parts.append(text[start:match.end()])
        start = match.end()
    parts.append(text[start:])

    return [
        part.strip()
        for part in parts
        if part.strip()
    ]


def split_long_sentence(
    sentence: str,
    max_chars: int,
) -> list[str]:
    """
    Split a sentence only when it exceeds the hard character limit.

    Prefer punctuation/whitespace boundaries before hard slicing.
    """

    sentence = sentence.strip()

    if not sentence:
        return []

    if len(sentence) <= max_chars:
        return [sentence]

    parts = re.split(
        r"(?<=[,;:，；：])\s*",
        sentence,
    )

    results: list[str] = []
    current = ""

    for part in parts:
        part = part.strip()

        if not part:
            continue

        candidate = (
            f"{current} {part}".strip()
            if current
            else part
        )

        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            results.append(current)
            current = ""

        while len(part) > max_chars:
            cut = part.rfind(
                " ",
                0,
                max_chars + 1,
            )

            if cut <= 0:
                cut = max_chars

            piece = part[:cut].strip()

            if piece:
                results.append(piece)

            part = part[cut:].strip()

        if part:
            current = part

    if current:
        results.append(current)

    return results


def build_chunks(
    text: str,
    config: ChunkingConfig | None = None,
) -> list[TextChunk]:
    """Build ordered paragraph-aware chunks."""

    config = config or ChunkingConfig()

    paragraphs = normalize_paragraphs(text)

    chunks: list[TextChunk] = []
    chunk_index = 0

    for paragraph_index, paragraph in enumerate(paragraphs):
        sentences = split_sentences(paragraph)

        expanded: list[str] = []

        for sentence in sentences:
            expanded.extend(
                split_long_sentence(
                    sentence,
                    config.max_chars,
                )
            )

        current: list[str] = []
        current_len = 0

        for sentence in expanded:
            sentence_len = len(sentence)

            if not current:
                current = [sentence]
                current_len = sentence_len
                continue

            candidate_len = (
                current_len
                + 1
                + sentence_len
            )

            should_flush = (
                len(current)
                >= config.max_sentences_per_chunk
                or candidate_len > config.max_chars
                or (
                    current_len >= config.target_chars
                    and sentence_len > 60
                )
            )

            if should_flush:
                chunks.append(
                    TextChunk(
                        index=chunk_index,
                        text=" ".join(current).strip(),
                        paragraph_index=paragraph_index,
                        sentence_count=len(current),
                        is_paragraph_end=False,
                    )
                )

                chunk_index += 1

                current = [sentence]
                current_len = sentence_len

            else:
                current.append(sentence)
                current_len = candidate_len

        if current:
            chunks.append(
                TextChunk(
                    index=chunk_index,
                    text=" ".join(current).strip(),
                    paragraph_index=paragraph_index,
                    sentence_count=len(current),
                    is_paragraph_end=True,
                )
            )

            chunk_index += 1

    return chunks
