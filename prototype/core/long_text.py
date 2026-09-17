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
    # Minimum standalone chunk length, in characters. 0 (the default)
    # disables the check entirely, so existing callers and configs are
    # unaffected unless they opt in explicitly. When set > 0, build_chunks()
    # merges any fragment shorter than this into an adjacent fragment
    # rather than emitting it as its own chunk -- see _merge_short_fragments().
    # This is a tunable candidate, not a settled constant: CP0.4-1 observed
    # two independent, reproducible content-fidelity failures on very short
    # standalone chunks (a 6-char hard-split remainder and a 9-char section
    # header) and floated 20-30 chars as a starting point to re-benchmark,
    # not a proven-correct threshold.
    min_chars: int = 0

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

        if self.min_chars < 0:
            raise ValueError(
                "min_chars must be >= 0"
            )

        if self.min_chars > self.max_chars:
            raise ValueError(
                "min_chars must be <= max_chars"
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

        if len(part) > max_chars:
            results.extend(
                _split_balanced(part, max_chars)
            )
        else:
            current = part

    if current:
        results.append(current)

    return results


def _split_balanced(text: str, max_chars: int) -> list[str]:
    """
    Hard-split ``text`` (already confirmed to exceed ``max_chars``) into
    word-safe, evenly-sized pieces.

    The previous implementation cut each piece as close to ``max_chars`` as
    possible before moving on, which is greedy and tends to leave a tiny,
    near-empty final piece once the leftover no longer divides evenly (e.g.
    a 564-char sentence hard-split at max_chars=160 left a lone 6-char
    trailing fragment, "chỉnh.", split out of the middle of the compound
    word "hoàn chỉnh" -- CP0.4-1). Such orphan fragments carry almost no
    linguistic context and were a reproducible, confirmed-failure-class
    input to TTS inference.

    Splitting into ``ceil(len(text) / max_chars)`` roughly equal pieces
    instead avoids that: every piece lands close to the same size, well
    under max_chars whenever the input isn't an exact multiple, and no
    piece is ever disproportionately small relative to the others. A word
    boundary near the balanced cut point is still preferred over a raw
    character cut; only text with no boundary at all (e.g. one long token)
    falls back to a hard cut, exactly as before.
    """

    text = text.strip()
    pieces: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_chars:
            pieces.append(remaining)
            break

        # Ceil division: how many pieces the remainder still needs, and
        # the balanced (<=max_chars) size that implies for this cut.
        pieces_left = -(-len(remaining) // max_chars)
        target = -(-len(remaining) // pieces_left)

        cut = remaining.rfind(" ", 0, target + 1)

        if cut <= 0:
            cut = remaining.find(" ", target)

            if cut == -1 or cut > max_chars:
                cut = target

        piece = remaining[:cut].strip()

        if piece:
            pieces.append(piece)

        remaining = remaining[cut:].strip()

    return pieces


def _merge_short_fragments(
    fragments: list[str],
    config: ChunkingConfig,
) -> list[str]:
    """
    Merge any fragment shorter than ``config.min_chars`` into an adjacent
    fragment, provided the merge does not exceed ``config.max_chars``.

    No-op when ``config.min_chars`` is 0 (the default), so this only ever
    changes output for callers that opt in.

    This deliberately applies uniformly to every fragment reaching
    build_chunks() -- a naturally short sentence (e.g. a 9-char section
    header like "PHẦN MỘT.") and a short remainder left over from
    split_long_sentence are treated the same way, since both were observed
    to fail at the same TTS inference stage (CP0.4-1). Preferring the
    previous fragment keeps reading order stable; falling back to the next
    fragment covers the case where there is no usable previous one (start
    of a paragraph). A fragment that cannot be merged without breaking
    max_chars is left standalone rather than dropped or truncated.

    Note: merging can leave a resulting chunk representing more than one
    original sentence even under a strict max_sentences_per_chunk=1
    config. That is an intentional trade-off -- shipping an ultra-short,
    minimal-context fragment to inference standalone is the confirmed
    problem this exists to avoid.
    """

    if config.min_chars <= 0 or len(fragments) < 2:
        return fragments

    merged = list(fragments)
    changed = True

    while changed:
        changed = False

        for i, fragment in enumerate(merged):
            if len(fragment) >= config.min_chars:
                continue

            prev_fits = (
                i > 0
                and len(merged[i - 1]) + 1 + len(fragment) <= config.max_chars
            )

            next_fits = (
                i + 1 < len(merged)
                and len(fragment) + 1 + len(merged[i + 1]) <= config.max_chars
            )

            if prev_fits:
                merged[i - 1] = f"{merged[i - 1]} {fragment}".strip()
                del merged[i]
            elif next_fits:
                merged[i + 1] = f"{fragment} {merged[i + 1]}".strip()
                del merged[i]
            else:
                # Cannot merge without breaking max_chars (min_chars is
                # close to max_chars, or both neighbors are already full).
                # Leave it standalone rather than dropping/truncating text.
                continue

            changed = True
            break

    return merged


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

        expanded = _merge_short_fragments(expanded, config)

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
