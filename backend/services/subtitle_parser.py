"""
Subtitle mining pipeline.

Steps:
  1. Parse ASS/SRT with pysubs2 (handles Shift-JIS via chardet)
  2. Tokenize with fugashi + ipadic (surface, lemma, POS, reading)
  3. Frequency analysis — lemma counts filtered to content words
  4. Register tagging — sentence-final particle heuristics
  5. JLPT cross-reference via SQLite vocabulary table
"""

import io
import re
import uuid
import chardet
from dataclasses import dataclass, field
from collections import Counter
from typing import Optional

import pysubs2

from models.schemas import SubtitleLine, VocabEntry

# Sentence-final particle register heuristics (textbook Appendix B)
REGISTER_PATTERNS = [
    (re.compile(r"[ぞぜ]$"), "masculine_assertion"),
    (re.compile(r"わ$"), "feminine_soft"),
    (re.compile(r"[なナ]$"), "casual"),
    (re.compile(r"って$"), "hearsay"),
    (re.compile(r"じゃん$"), "casual_masculine"),
    (re.compile(r"ッ$"), "clipped"),
]

# Stop-word POS tags to exclude from frequency analysis
STOP_POS = {"助詞", "助動詞", "記号", "感動詞", "接続詞"}

# POS tags to include (content words only)
CONTENT_POS = {"名詞", "動詞", "形容詞", "形容動詞"}


@dataclass
class Token:
    surface: str
    lemma: str
    pos: str
    reading: str


def _detect_encoding(raw: bytes) -> str:
    result = chardet.detect(raw)
    enc = result.get("encoding") or "utf-8"
    # Normalize common CJK encoding aliases
    if enc.lower() in {"shift_jis", "shift-jis", "sjis", "x-sjis"}:
        enc = "shift_jis_2004"
    return enc


def parse_file(file_bytes: bytes, filename: str) -> list[SubtitleLine]:
    """Parse ASS or SRT bytes into a list of SubtitleLine objects."""
    encoding = _detect_encoding(file_bytes)
    text = file_bytes.decode(encoding, errors="replace")

    ext = filename.rsplit(".", 1)[-1].lower()
    fmt = "ass" if ext in {"ass", "ssa"} else "srt"

    subs = pysubs2.SSAFile.from_string(text, format_=fmt)

    lines: list[SubtitleLine] = []
    for i, event in enumerate(subs.events):
        if event.is_comment or not event.text.strip():
            continue
        clean = pysubs2.SSAFile.from_string(
            f"[Script Info]\n[Events]\nDialogue: 0,{event.start},{event.end},Default,,0,0,0,,{event.text}",
            format_="ass",
        ).events[0].plaintext.strip()
        if clean:
            lines.append(
                SubtitleLine(
                    index=i,
                    start_ms=event.start,
                    end_ms=event.end,
                    text=clean,
                    register=_tag_register(clean),
                )
            )
    return lines


def _tag_register(text: str) -> str:
    """Classify the register of a subtitle line via sentence-final particle heuristics."""
    stripped = text.strip()
    for pattern, tag in REGISTER_PATTERNS:
        if pattern.search(stripped):
            return tag
    return "neutral"


def tokenize(lines: list[SubtitleLine]) -> list[Token]:
    """Tokenize all subtitle lines using fugashi + ipadic."""
    try:
        import fugashi
        tagger = fugashi.Tagger()
    except ImportError:
        # Graceful degradation if fugashi not installed
        return []

    tokens: list[Token] = []
    for line in lines:
        for word in tagger(line.text):
            feature = word.feature
            pos = feature[0] if len(feature) > 0 else "その他"
            lemma = feature[6] if len(feature) > 6 and feature[6] != "*" else word.surface
            reading = feature[7] if len(feature) > 7 and feature[7] != "*" else word.surface
            tokens.append(Token(
                surface=word.surface,
                lemma=lemma,
                pos=pos,
                reading=reading,
            ))
    return tokens


def frequency_analysis(tokens: list[Token]) -> dict[str, int]:
    """Count lemma frequency for content-word POS tags only."""
    counter: Counter = Counter()
    for tok in tokens:
        if tok.pos in CONTENT_POS and len(tok.lemma) > 1:
            counter[tok.lemma] += 1
    return dict(counter.most_common())


def cross_reference_jlpt(
    lemma_freq: dict[str, int],
    db_session,
    show_id: str,
    lines: list[SubtitleLine],
) -> list[VocabEntry]:
    """Join frequency data with SQLite vocabulary for JLPT levels and meanings."""
    from db import VocabularyEntry

    results: list[VocabEntry] = []

    # Build a lookup of example sentences per lemma
    example_map: dict[str, str] = {}
    for line in lines:
        for lemma in lemma_freq:
            if lemma in line.text and lemma not in example_map:
                example_map[lemma] = line.text

    for lemma, freq in sorted(lemma_freq.items(), key=lambda x: -x[1]):
        entry = (
            db_session.query(VocabularyEntry)
            .filter(VocabularyEntry.lemma == lemma)
            .first()
        )
        results.append(
            VocabEntry(
                lemma=lemma,
                reading=entry.reading if entry else None,
                meaning=entry.meaning if entry else None,
                jlpt_level=entry.jlpt_level if entry else None,
                frequency=freq,
                example_sentence=example_map.get(lemma),
            )
        )

    return results


class SubtitlePipeline:
    """End-to-end subtitle processing pipeline."""

    def run(
        self,
        file_bytes: bytes,
        filename: str,
        show_id: str,
        db_session,
    ) -> tuple[list[SubtitleLine], list[VocabEntry]]:
        lines = parse_file(file_bytes, filename)
        tokens = tokenize(lines)
        freq = frequency_analysis(tokens)
        vocab = cross_reference_jlpt(freq, db_session, show_id, lines)
        return lines, vocab
