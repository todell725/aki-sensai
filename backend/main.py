"""
Aki-Sensei FastAPI application entry point.

Startup sequence:
  1. Initialize SQLite database tables
  2. Warm up Whisper and Silero-VAD models
  3. Register all routers

Health check: GET /health
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import init_db
from routers import chat, voice, subtitles, drills
from services import stt as stt_svc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aki-sensei")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    init_db()
    logger.info("Database ready.")

    logger.info("Warming up STT models (Silero-VAD + Whisper)...")
    try:
        stt_svc.warmup()
        logger.info("STT models loaded.")
    except Exception as e:
        logger.warning(f"STT warmup failed (non-fatal): {e}")

    yield
    logger.info("Shutting down Aki-Sensei.")


app = FastAPI(
    title="Aki-Sensei API",
    description="Local Anime Fluency Engine — privacy-first Japanese learning backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(voice.router)
app.include_router(subtitles.router)
app.include_router(drills.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "aki-sensei"}


@app.get("/metrics")
def metrics():
    """Return basic session metrics for dashboard."""
    from db import SessionLocal, SessionLog, FailureLog
    from sqlalchemy import func

    db = SessionLocal()
    try:
        total_sessions = db.query(SessionLog).count()
        total_turns = db.query(func.sum(SessionLog.turn_count)).scalar() or 0
        productive_turns = db.query(func.sum(SessionLog.productive_turns)).scalar() or 0
        avg_duration = db.query(func.avg(SessionLog.duration_s)).scalar() or 0

        # Recent sessions for trend
        recent = (
            db.query(SessionLog)
            .order_by(SessionLog.started_at.desc())
            .limit(30)
            .all()
        )

        session_data = [
            {
                "date": s.started_at.isoformat() if s.started_at else None,
                "turn_count": s.turn_count,
                "productive_turns": s.productive_turns,
                "productive_ratio": round(s.productive_turns / s.turn_count, 3)
                if s.turn_count > 0 else 0,
                "duration_s": s.duration_s,
            }
            for s in recent
        ]

        # Top failure patterns
        failure_patterns = (
            db.query(
                FailureLog.pattern,
                func.count(FailureLog.pattern).label("cnt"),
            )
            .filter(FailureLog.pattern.isnot(None))
            .group_by(FailureLog.pattern)
            .order_by(func.count(FailureLog.pattern).desc())
            .limit(10)
            .all()
        )

        return {
            "total_sessions": total_sessions,
            "total_turns": total_turns,
            "productive_ratio": round(productive_turns / total_turns, 3)
            if total_turns > 0 else 0,
            "avg_session_duration_s": round(avg_duration, 1),
            "recent_sessions": session_data,
            "top_failure_patterns": [
                {"pattern": row.pattern, "count": row.cnt}
                for row in failure_patterns
            ],
        }
    finally:
        db.close()
