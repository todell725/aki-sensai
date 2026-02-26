"""
SRS drill router.

GET  /drills/due              — get due cards (up to 10)
POST /drills/{card_id}/review — mark card correct or incorrect
GET  /drills/stats            — box distribution, accuracy, graduation count
GET  /drills/shadowing/{show_id} — get subtitle lines for shadowing session
POST /drills/shadowing/compare   — compare shadowing attempt pitch
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from db import get_db, FailureLog
from datetime import datetime
from models.schemas import SRSCard, DrillReviewRequest, DrillStatsResponse, PitchCompareResponse
from services.srs import LeitnerScheduler
from services.tts import synthesize_async
from services.pitch import get_pitch_contour_async, compare_contours_async
from fastapi.responses import Response

router = APIRouter(prefix="/drills", tags=["drills"])


@router.get("/due", response_model=list[SRSCard])
def get_due_cards(db: Session = Depends(get_db)):
    """Return up to 10 cards due for review today."""
    scheduler = LeitnerScheduler(db)
    return scheduler.get_due_cards(limit=10)


@router.post("/{card_id}/review", response_model=SRSCard)
def review_card(
    card_id: int,
    req: DrillReviewRequest,
    db: Session = Depends(get_db),
):
    """Submit a review result for a card. Updates its Leitner box and next review date."""
    scheduler = LeitnerScheduler(db)
    try:
        return scheduler.review_card(card_id, req.correct)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/stats", response_model=DrillStatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """Return SRS statistics: box distribution, accuracy rate, graduation count."""
    scheduler = LeitnerScheduler(db)
    stats = scheduler.get_stats()
    return DrillStatsResponse(**stats)


@router.get("/shadowing/{show_id}")
def get_shadowing_lines(
    show_id: str,
    limit: int = 5,
    db: Session = Depends(get_db),
):
    """Get subtitle lines for a shadowing session."""
    from db import SRSCard as SRSCardModel

    cards = (
        db.query(SRSCardModel)
        .filter(
            SRSCardModel.show_id == show_id,
            SRSCardModel.example_sentence.isnot(None),
        )
        .order_by(SRSCardModel.frequency.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "card_id": c.id,
            "lemma": c.lemma,
            "sentence": c.example_sentence,
            "affect_tag": c.affect_tag,
        }
        for c in cards
    ]


@router.post("/shadowing/{card_id}/speak")
async def speak_shadowing_line(card_id: int, db: Session = Depends(get_db)):
    """Synthesize a shadowing sentence to WAV for the user to shadow."""
    from db import SRSCard as SRSCardModel

    card = db.query(SRSCardModel).filter(SRSCardModel.id == card_id).first()
    if not card or not card.example_sentence:
        raise HTTPException(status_code=404, detail="Card or sentence not found")

    wav_bytes = await synthesize_async(card.example_sentence)
    return Response(content=wav_bytes, media_type="audio/wav")


@router.post("/shadowing/{card_id}/compare", response_model=PitchCompareResponse)
async def compare_shadowing(
    card_id: int,
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Compare user shadowing attempt against TTS reference pitch."""
    from db import SRSCard as SRSCardModel

    card = db.query(SRSCardModel).filter(SRSCardModel.id == card_id).first()
    if not card or not card.example_sentence:
        raise HTTPException(status_code=404, detail="Card or sentence not found")

    attempt_bytes = await audio_file.read()
    reference = await get_pitch_contour_async(card.example_sentence)
    result = await compare_contours_async(reference.pattern, attempt_bytes)

    # Log pitch mismatches to failure_log
    if result.match_ratio < 0.5:
        log = FailureLog(
            pattern=f"pitch_mismatch:{card.lemma}",
            timestamp=datetime.utcnow(),
        )
        db.add(log)
        db.commit()

    return result
