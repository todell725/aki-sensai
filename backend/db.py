from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from datetime import datetime

from config import settings

engine = create_engine(
    f"sqlite:///{settings.sqlite_path}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class SessionLog(Base):
    __tablename__ = "session_log"
    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    turn_count = Column(Integer, default=0)
    productive_turns = Column(Integer, default=0)
    duration_s = Column(Float, default=0.0)
    grammar_level = Column(String, default="N5")
    tone_mode = Column(String, default="textbook")


class FailureLog(Base):
    __tablename__ = "failure_log"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("session_log.id"), nullable=True)
    word = Column(String, nullable=True)
    pattern = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    whisper_confidence = Column(Float, nullable=True)


class SRSCard(Base):
    __tablename__ = "srs_cards"
    id = Column(Integer, primary_key=True, index=True)
    show_id = Column(String, nullable=True)
    lemma = Column(String, index=True)
    reading = Column(String, nullable=True)
    meaning = Column(String, nullable=True)
    jlpt_level = Column(String, nullable=True)
    frequency = Column(Integer, default=1)
    box = Column(Integer, default=1)
    next_review = Column(DateTime, default=datetime.utcnow)
    exposures = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    wrong_count = Column(Integer, default=0)
    affect_tag = Column(String, nullable=True)
    example_sentence = Column(String, nullable=True)


class VocabularyEntry(Base):
    __tablename__ = "vocabulary"
    id = Column(Integer, primary_key=True, index=True)
    lemma = Column(String, index=True)
    reading = Column(String, nullable=True)
    meaning = Column(String, nullable=True)
    jlpt_level = Column(String, nullable=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
