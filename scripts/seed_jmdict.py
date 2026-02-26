#!/usr/bin/env python3
"""
JMdict vocabulary seeder.

Downloads or reads JMdict XML (Electronic Dictionary Research and Development Group)
and populates the SQLite vocabulary table with kanji, reading, gloss, and JLPT level.

Usage:
  python seed_jmdict.py --xml path/to/JMdict.xml
  python seed_jmdict.py --download  # attempts to download from edrdg.org mirror

JMdict is licensed under Creative Commons Attribution-ShareAlike 4.0.
"""

import argparse
import sys
import os
import xml.etree.ElementTree as ET
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from config import settings
from db import init_db, SessionLocal, VocabularyEntry

# Map JMdict misc field values to JLPT levels
JLPT_MISC_MAP = {
    "jlpt-n5": "N5",
    "jlpt-n4": "N4",
    "jlpt-n3": "N3",
    "jlpt-n2": "N2",
    "jlpt-n1": "N1",
}


def parse_jmdict(xml_path: str, limit: Optional[int] = None) -> list[dict]:
    """Parse JMdict XML and extract vocab entries with JLPT level."""
    print(f"Parsing JMdict: {xml_path}")
    tree = ET.parse(xml_path)
    root = tree.getroot()

    entries = []
    for i, entry in enumerate(root.findall("entry")):
        if limit and i >= limit:
            break

        # Kanji form
        kanji = ""
        kele = entry.find("k_ele/keb")
        if kele is not None and kele.text:
            kanji = kele.text

        # Reading form
        reading = ""
        rele = entry.find("r_ele/reb")
        if rele is not None and rele.text:
            reading = rele.text

        lemma = kanji or reading
        if not lemma:
            continue

        # First English gloss
        meaning = ""
        gloss = entry.find("sense/gloss")
        if gloss is not None and gloss.text:
            meaning = gloss.text

        # JLPT level from misc tags
        jlpt_level = None
        for misc in entry.findall("sense/misc"):
            if misc.text and misc.text in JLPT_MISC_MAP:
                jlpt_level = JLPT_MISC_MAP[misc.text]
                break

        entries.append({
            "lemma": lemma,
            "reading": reading if reading != lemma else None,
            "meaning": meaning,
            "jlpt_level": jlpt_level,
        })

    return entries


def download_jmdict(output_path: str) -> bool:
    """Attempt to download JMdict from FTP mirror."""
    import urllib.request
    import gzip
    import shutil

    url = "http://ftp.edrdg.org/pub/Nihongo/JMdict.gz"
    gz_path = output_path + ".gz"

    try:
        print(f"Downloading JMdict from {url}...")
        urllib.request.urlretrieve(url, gz_path)
        print("Decompressing...")
        with gzip.open(gz_path, "rb") as f_in:
            with open(output_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(gz_path)
        print(f"Saved to {output_path}")
        return True
    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)
        return False


def seed_db(entries: list[dict], db) -> int:
    """Upsert vocabulary entries into SQLite. Returns count inserted."""
    inserted = 0
    batch_size = 500

    for i in range(0, len(entries), batch_size):
        batch = entries[i : i + batch_size]
        for entry in batch:
            existing = (
                db.query(VocabularyEntry)
                .filter(VocabularyEntry.lemma == entry["lemma"])
                .first()
            )
            if not existing:
                db.add(VocabularyEntry(**entry))
                inserted += 1
            elif entry.get("jlpt_level") and not existing.jlpt_level:
                existing.jlpt_level = entry["jlpt_level"]

        db.commit()
        print(f"  Processed {min(i + batch_size, len(entries))}/{len(entries)} entries...")

    return inserted


def main():
    parser = argparse.ArgumentParser(description="Seed SQLite vocabulary table from JMdict")
    parser.add_argument("--xml", default="", help="Path to JMdict XML file")
    parser.add_argument("--download", action="store_true", help="Download JMdict automatically")
    parser.add_argument("--limit", type=int, default=0, help="Limit entries (0 = no limit)")
    args = parser.parse_args()

    xml_path = args.xml

    if args.download:
        xml_path = xml_path or "/tmp/JMdict.xml"
        if not os.path.exists(xml_path):
            if not download_jmdict(xml_path):
                sys.exit(1)

    if not xml_path or not os.path.exists(xml_path):
        print("Error: provide --xml path or use --download", file=sys.stderr)
        sys.exit(1)

    init_db()
    db = SessionLocal()

    entries = parse_jmdict(xml_path, limit=args.limit or None)
    print(f"Parsed {len(entries)} dictionary entries")

    print("Seeding database...")
    inserted = seed_db(entries, db)
    db.close()

    print(f"\nDone. Inserted {inserted} new vocabulary entries.")


if __name__ == "__main__":
    main()
