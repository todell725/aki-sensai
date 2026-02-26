#!/usr/bin/env python3
"""
Subtitle ingestion pipeline.

Usage:
  python ingest_subtitles.py --file episode01.ass --show "Demon Slayer" [--episodes ep02.ass ep03.ass ...]

Processes ASS/SRT subtitle files, extracts frequency-ranked vocabulary,
stores results in SQLite (SRS cards) and ChromaDB (semantic search).
"""

import argparse
import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from config import settings
from db import init_db, SessionLocal, SRSCard
from services.subtitle_parser import SubtitlePipeline
from services.rag import RAGService


def main():
    parser = argparse.ArgumentParser(description="Ingest anime subtitle files")
    parser.add_argument("--file", required=True, nargs="+", help="ASS or SRT file(s) to ingest")
    parser.add_argument("--show", required=True, help="Show name (e.g. 'Demon Slayer')")
    parser.add_argument("--show-id", default="", help="Optional fixed show ID (auto-generated if omitted)")
    parser.add_argument("--top-n", type=int, default=200, help="Top N vocab entries to store as SRS cards")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    pipeline = SubtitlePipeline()
    rag = RAGService()

    show_id = args.show_id or str(uuid.uuid4())[:8]
    print(f"Show: '{args.show}' (ID: {show_id})")

    all_lines = []
    for filepath in args.file:
        if not os.path.exists(filepath):
            print(f"Warning: file not found: {filepath}", file=sys.stderr)
            continue
        print(f"  Processing: {filepath}")
        with open(filepath, "rb") as f:
            content = f.read()
        filename = os.path.basename(filepath)
        lines, _ = pipeline.run(content, filename, show_id, db)
        all_lines.extend(lines)
        print(f"    → {len(lines)} subtitle lines")

    if not all_lines:
        print("No lines found. Exiting.")
        sys.exit(1)

    # Re-run full pipeline on combined lines for accurate frequency counts
    print(f"\nRunning frequency analysis across {len(all_lines)} total lines...")
    from services.subtitle_parser import tokenize, frequency_analysis, cross_reference_jlpt
    tokens = tokenize(all_lines)
    freq = frequency_analysis(tokens)
    vocab = cross_reference_jlpt(freq, db, show_id, all_lines)

    print(f"Unique content lemmas: {len(vocab)}")
    print(f"Top 10 by frequency:")
    for entry in vocab[:10]:
        print(f"  {entry.lemma} ({entry.frequency}x) — {entry.meaning or 'unknown'} [{entry.jlpt_level or '?'}]")

    # Store top-N as SRS cards
    stored = 0
    for entry in vocab[:args.top_n]:
        existing = (
            db.query(SRSCard)
            .filter(SRSCard.show_id == show_id, SRSCard.lemma == entry.lemma)
            .first()
        )
        if not existing:
            card = SRSCard(
                show_id=show_id,
                lemma=entry.lemma,
                reading=entry.reading,
                meaning=entry.meaning,
                jlpt_level=entry.jlpt_level,
                frequency=entry.frequency,
                example_sentence=entry.example_sentence,
                box=1,
            )
            db.add(card)
            stored += 1

        # Also store in ChromaDB
        rag.add_vocab(
            word=entry.lemma,
            reading=entry.reading or "",
            meaning=entry.meaning or "",
            jlpt_level=entry.jlpt_level or "",
            frequency=entry.frequency,
            show_id=show_id,
        )

    db.commit()
    db.close()

    print(f"\nStored {stored} new SRS cards for show '{args.show}' (ID: {show_id})")
    print(f"Use show ID '{show_id}' in the app to access vocabulary and shadowing lines.")


if __name__ == "__main__":
    main()
