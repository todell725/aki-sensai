#!/usr/bin/env python3
"""
Textbook PDF ingestion pipeline.

Usage:
  python ingest_textbook.py --pdf path/to/textbook.pdf --level N5 --chapter "Chapter 1"

Reads a Japanese textbook PDF, chunks the text, embeds with sentence-transformers,
and stores in ChromaDB for RAG grammar retrieval.
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from config import settings
from services.rag import RAGService


def extract_text(pdf_path: str) -> list[dict]:
    """Extract text from a PDF page by page using pdfplumber."""
    import pdfplumber

    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and text.strip():
                pages.append({
                    "text": text.strip(),
                    "page": i + 1,
                })
    return pages


def chunk_text(
    pages: list[dict],
    chunk_size: int = 500,
    overlap: int = 50,
    level: str = "N5",
    source: str = "",
) -> list[dict]:
    """
    Chunk page text with token overlap.
    Each chunk inherits the page metadata.
    """
    chunks = []
    for page in pages:
        text = page["text"]
        words = text.split()

        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text_str = " ".join(words[start:end])

            if len(chunk_text_str.strip()) > 20:  # Skip tiny chunks
                chunks.append({
                    "text": chunk_text_str,
                    "level": level,
                    "page": page["page"],
                    "chapter": _detect_chapter(chunk_text_str),
                    "source": source,
                })

            start += chunk_size - overlap

    return chunks


def _detect_chapter(text: str) -> str:
    """Heuristically extract a chapter or section label from the chunk."""
    import re
    # Look for Japanese chapter markers
    patterns = [
        r"第[一二三四五六七八九十\d]+[章課節]",
        r"Chapter\s+\d+",
        r"Unit\s+\d+",
        r"Lesson\s+\d+",
        r"レッスン\d+",
    ]
    for pattern in patterns:
        match = re.search(pattern, text[:100])
        if match:
            return match.group(0)
    return ""


def embed_and_store(chunks: list[dict], rag: RAGService) -> int:
    """Batch embed and store chunks in ChromaDB. Returns count stored."""
    batch_size = 32
    total = 0

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        rag.add_textbook_chunks_batch(batch)
        total += len(batch)
        print(f"  Stored {total}/{len(chunks)} chunks...")

    return total


def main():
    parser = argparse.ArgumentParser(description="Ingest a Japanese textbook PDF into ChromaDB")
    parser.add_argument("--pdf", required=True, help="Path to textbook PDF")
    parser.add_argument("--level", default="N5", choices=["N5", "N4", "N3", "N2", "N1"],
                        help="JLPT level of this textbook")
    parser.add_argument("--chunk-size", type=int, default=500, help="Tokens per chunk")
    parser.add_argument("--overlap", type=int, default=50, help="Overlap tokens between chunks")
    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        print(f"Error: PDF not found: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading PDF: {args.pdf}")
    pages = extract_text(args.pdf)
    print(f"Extracted {len(pages)} pages")

    source = os.path.basename(args.pdf)
    chunks = chunk_text(pages, args.chunk_size, args.overlap, args.level, source)
    print(f"Generated {len(chunks)} chunks (level={args.level})")

    print("Connecting to ChromaDB...")
    rag = RAGService()

    print("Embedding and storing chunks...")
    stored = embed_and_store(chunks, rag)

    print(f"\nDone. Stored {stored} chunks from '{source}' at level {args.level}.")


if __name__ == "__main__":
    main()
