from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── Chat / Speak ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    tone_mode: str = "textbook"          # "textbook" | "anime"
    grammar_level: str = "N5"            # N5 | N4 | N3 | N2 | N1
    task: str = "free_conversation"      # "free_conversation" | "shadowing" | "drill" | "grammar_focus"
    session_id: Optional[int] = None


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class SpeakRequest(BaseModel):
    text: str


class TranscriptFrame(BaseModel):
    type: str   # "transcript" | "tts_start" | "tts_end" | "error" | "latency"
    text: Optional[str] = None
    data: Optional[dict] = None


# ── Subtitles ─────────────────────────────────────────────────────────────────

class SubtitleLine(BaseModel):
    index: int
    start_ms: int
    end_ms: int
    text: str
    register: Optional[str] = None       # "masculine_assertion" | "feminine_soft" | "casual" | "neutral"


class VocabEntry(BaseModel):
    lemma: str
    reading: Optional[str] = None
    meaning: Optional[str] = None
    jlpt_level: Optional[str] = None
    frequency: int = 1
    affect_tag: Optional[str] = None
    example_sentence: Optional[str] = None


class SubtitleUploadResponse(BaseModel):
    show_id: str
    show_name: str
    total_lines: int
    unique_lemmas: int
    top_vocab: List[VocabEntry]


# ── SRS / Drills ──────────────────────────────────────────────────────────────

class SRSCard(BaseModel):
    id: int
    show_id: Optional[str] = None
    lemma: str
    reading: Optional[str] = None
    meaning: Optional[str] = None
    jlpt_level: Optional[str] = None
    frequency: int
    box: int
    next_review: datetime
    exposures: int
    correct_count: int
    wrong_count: int
    affect_tag: Optional[str] = None
    example_sentence: Optional[str] = None

    class Config:
        from_attributes = True


class DrillReviewRequest(BaseModel):
    correct: bool


class DrillStatsResponse(BaseModel):
    box_distribution: dict
    total_cards: int
    accuracy_rate: float
    graduated_this_week: int
    due_count: int


# ── Pitch ─────────────────────────────────────────────────────────────────────

class PitchContour(BaseModel):
    text: str
    morae: List[str]
    pattern: List[int]           # 0=flat, 1=rise, 2=drop per mora


class PitchCompareResponse(BaseModel):
    match_ratio: float
    mismatched_morae: List[int]  # indices of mismatched morae
    reference_pattern: List[int]
    attempt_pattern: List[float]


# ── Session / Metrics ─────────────────────────────────────────────────────────

class SessionStats(BaseModel):
    session_id: int
    turn_count: int
    productive_turns: int
    productive_ratio: float
    duration_s: float
    started_at: datetime


class LatencyReport(BaseModel):
    vad_ms: float
    stt_ms: float
    llm_ttft_ms: float
    tts_ms: float
    total_ms: float
