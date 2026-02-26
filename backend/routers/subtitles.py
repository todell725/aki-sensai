"""
Subtitle upload and vocabulary analysis router.

POST /subtitles/upload                 — upload ASS/SRT file, run full pipeline
GET  /subtitles/{show_id}/vocab        — get frequency-ranked vocabulary list
GET  /subtitles/{show_id}/lines        — get example sentences for a word
POST /subtitles/{show_id}/add-to-srs   — create SRS cards for selected vocab
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_db, SRSCard as SRSCardModel
from models.schemas import SubtitleUploadResponse, VocabEntry
from services.subtitle_parser import SubtitlePipeline
from services.srs import LeitnerScheduler
from services.rag import get_rag

router = APIRouter(prefix="/subtitles", tags=["subtitles"])

_pipeline = SubtitlePipeline()


@router.post("/upload", response_model=SubtitleUploadResponse)
async def upload_subtitles(
    file: UploadFile = File(...),
    show_name: str = Form(...),
    db: Session = Depends(get_db),
):
    """Upload an ASS or SRT subtitle file and run the mining pipeline."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in {"ass", "ssa", "srt"}:
        raise HTTPException(status_code=400, detail="Only .ass, .ssa, and .srt files are supported")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    show_id = str(uuid.uuid4())[:8]

    lines, vocab = _pipeline.run(
        file_bytes=content,
        filename=file.filename,
        show_id=show_id,
        db_session=db,
    )

    # Store vocab in ChromaDB for future semantic search
    rag = get_rag()
    for entry in vocab[:200]:  # Store top 200 by frequency
        rag.add_vocab(
            word=entry.lemma,
            reading=entry.reading or "",
            meaning=entry.meaning or "",
            jlpt_level=entry.jlpt_level or "",
            frequency=entry.frequency,
            show_id=show_id,
        )

    return SubtitleUploadResponse(
        show_id=show_id,
        show_name=show_name,
        total_lines=len(lines),
        unique_lemmas=len(vocab),
        top_vocab=vocab[:20],
    )


@router.get("/{show_id}/vocab", response_model=list[VocabEntry])
def get_vocab(
    show_id: str,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    """Return frequency-ranked vocabulary list for a show."""
    cards = (
        db.query(SRSCardModel)
        .filter(SRSCardModel.show_id == show_id)
        .order_by(SRSCardModel.frequency.desc())
        .limit(limit)
        .all()
    )
    return [
        VocabEntry(
            lemma=c.lemma,
            reading=c.reading,
            meaning=c.meaning,
            jlpt_level=c.jlpt_level,
            frequency=c.frequency,
            affect_tag=c.affect_tag,
            example_sentence=c.example_sentence,
        )
        for c in cards
    ]


@router.get("/{show_id}/lines")
def get_example_lines(
    show_id: str,
    word: str = Query(..., description="Lemma to search for"),
    db: Session = Depends(get_db),
):
    """Return example sentences containing a specific word."""
    card = (
        db.query(SRSCardModel)
        .filter(SRSCardModel.show_id == show_id, SRSCardModel.lemma == word)
        .first()
    )
    if not card:
        return {"lines": []}
    return {"lines": [card.example_sentence] if card.example_sentence else []}


@router.post("/{show_id}/add-to-srs")
def add_to_srs(
    show_id: str,
    lemmas: list[str],
    db: Session = Depends(get_db),
):
    """Create SRS cards for selected vocabulary items."""
    scheduler = LeitnerScheduler(db)
    added = 0

    for lemma in lemmas:
        card = (
            db.query(SRSCardModel)
            .filter(SRSCardModel.show_id == show_id, SRSCardModel.lemma == lemma)
            .first()
        )
        if card:
            scheduler.add_card(
                lemma=card.lemma,
                reading=card.reading,
                meaning=card.meaning,
                jlpt_level=card.jlpt_level,
                frequency=card.frequency,
                show_id=show_id,
                affect_tag=card.affect_tag,
                example_sentence=card.example_sentence,
            )
            added += 1

    return {"added": added}
