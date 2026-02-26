"""
Leitner spaced repetition scheduler backed by SQLite.

Box intervals (days): [1, 2, 4, 8, 16]
- Correct answer → advance one box (max box 5)
- Wrong answer   → reset to box 1
- Cards in box 5 are considered "graduated" and reviewed at 16-day intervals.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from db import SRSCard as SRSCardModel
from models.schemas import SRSCard

BOX_INTERVALS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}


class LeitnerScheduler:
    def __init__(self, db: Session):
        self.db = db

    def get_due_cards(self, limit: int = 10) -> list[SRSCard]:
        now = datetime.utcnow()
        cards = (
            self.db.query(SRSCardModel)
            .filter(SRSCardModel.next_review <= now)
            .order_by(SRSCardModel.next_review.asc())
            .limit(limit)
            .all()
        )
        return [SRSCard.model_validate(c) for c in cards]

    def review_card(self, card_id: int, correct: bool) -> SRSCard:
        card = self.db.query(SRSCardModel).filter(SRSCardModel.id == card_id).first()
        if not card:
            raise ValueError(f"Card {card_id} not found")

        if correct:
            card.correct_count += 1
            card.box = min(card.box + 1, 5)
        else:
            card.wrong_count += 1
            card.box = 1

        interval_days = BOX_INTERVALS[card.box]
        card.next_review = datetime.utcnow() + timedelta(days=interval_days)
        card.exposures += 1

        self.db.commit()
        self.db.refresh(card)
        return SRSCard.model_validate(card)

    def add_card(
        self,
        lemma: str,
        reading: Optional[str] = None,
        meaning: Optional[str] = None,
        jlpt_level: Optional[str] = None,
        frequency: int = 1,
        show_id: Optional[str] = None,
        affect_tag: Optional[str] = None,
        example_sentence: Optional[str] = None,
    ) -> SRSCard:
        existing = (
            self.db.query(SRSCardModel)
            .filter(SRSCardModel.lemma == lemma, SRSCardModel.show_id == show_id)
            .first()
        )
        if existing:
            # Update frequency if card already exists
            existing.frequency = max(existing.frequency, frequency)
            self.db.commit()
            return SRSCard.model_validate(existing)

        card = SRSCardModel(
            lemma=lemma,
            reading=reading,
            meaning=meaning,
            jlpt_level=jlpt_level,
            frequency=frequency,
            show_id=show_id,
            box=1,
            next_review=datetime.utcnow(),
            exposures=0,
            correct_count=0,
            wrong_count=0,
            affect_tag=affect_tag,
            example_sentence=example_sentence,
        )
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)
        return SRSCard.model_validate(card)

    def get_stats(self) -> dict:
        from sqlalchemy import func
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)

        # Box distribution
        box_dist = {}
        for box in range(1, 6):
            count = (
                self.db.query(SRSCardModel)
                .filter(SRSCardModel.box == box)
                .count()
            )
            box_dist[str(box)] = count

        total = self.db.query(SRSCardModel).count()

        # Accuracy rate
        total_reviews = self.db.query(
            func.sum(SRSCardModel.correct_count + SRSCardModel.wrong_count)
        ).scalar() or 0
        total_correct = self.db.query(func.sum(SRSCardModel.correct_count)).scalar() or 0
        accuracy = total_correct / total_reviews if total_reviews > 0 else 0.0

        # Graduated this week (box 5 cards with recent reviews)
        graduated = (
            self.db.query(SRSCardModel)
            .filter(SRSCardModel.box == 5, SRSCardModel.next_review >= week_ago)
            .count()
        )

        # Due count
        due_count = (
            self.db.query(SRSCardModel)
            .filter(SRSCardModel.next_review <= now)
            .count()
        )

        return {
            "box_distribution": box_dist,
            "total_cards": total,
            "accuracy_rate": round(accuracy, 3),
            "graduated_this_week": graduated,
            "due_count": due_count,
        }
