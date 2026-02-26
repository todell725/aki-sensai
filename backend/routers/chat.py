"""
Chat and TTS routers.

POST /chat   — streaming text conversation with Aki-Sensei
POST /speak  — text-to-speech synthesis, returns WAV bytes
POST /pitch  — pitch contour analysis for a text string
POST /pitch/compare — compare user audio against reference pitch
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session

from db import get_db, SessionLog, FailureLog
from models.schemas import (
    ChatRequest, ChatMessage, SpeakRequest,
    PitchContour, PitchCompareResponse,
)
from services import llm, tts, pitch as pitch_svc
from services.rag import get_rag
from services.memory import get_context, get_recurring_errors
from prompts.sensei import build_system_prompt

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    """Streaming Japanese conversation with Aki-Sensei."""
    rag = get_rag()

    # Retrieve RAG grammar context
    rag_chunks = rag.query_grammar(req.message, req.grammar_level)
    error_log = get_recurring_errors(db)
    session_memory = await get_context()

    system_prompt = build_system_prompt(
        rag_chunks=rag_chunks,
        tone_mode=req.tone_mode,
        error_log=error_log,
        task=req.task,
        session_memory=session_memory,
    )

    messages = [{"role": "user", "content": req.message}]

    async def token_generator():
        full_response = []
        async for token in llm.stream_chat(messages, system_prompt):
            full_response.append(token)
            yield token

        # Log fallback detections
        response_text = "".join(full_response)
        if llm.contains_fallback(response_text) and req.session_id:
            log = FailureLog(
                session_id=req.session_id,
                pattern="fallback_triggered",
            )
            db.add(log)
            db.commit()

    return StreamingResponse(token_generator(), media_type="text/plain; charset=utf-8")


@router.post("/speak")
async def speak(req: SpeakRequest):
    """Synthesize Japanese text to WAV audio."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        wav_bytes = await tts.synthesize_async(req.text)
        return Response(content=wav_bytes, media_type="audio/wav")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/pitch/analyze", response_model=PitchContour)
async def analyze_pitch(req: SpeakRequest):
    """Return pitch accent contour for Japanese text."""
    return await pitch_svc.get_pitch_contour_async(req.text)


@router.post("/pitch/compare", response_model=PitchCompareResponse)
async def compare_pitch(reference_pattern: list[int], audio_bytes: bytes):
    """Compare user audio against a reference pitch pattern."""
    return await pitch_svc.compare_contours_async(reference_pattern, audio_bytes)
