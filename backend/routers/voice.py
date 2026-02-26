"""
WebSocket voice loop router.

Protocol:
  Browser → backend: binary PCM frames (16kHz, mono, int16)
  Backend → browser:
    - binary frames: WAV audio chunks from TTS
    - text frames: JSON control messages
      {"type": "transcript", "text": "..."}
      {"type": "tts_start"}
      {"type": "tts_end"}
      {"type": "latency", "data": {...}}
      {"type": "error", "text": "..."}

Latency pipeline:
  PCM chunks → VADState → Whisper → RAG → LLM stream → sentence_stream → asyncio.Queue → Piper TTS → WAV chunks
"""

import asyncio
import json
import time
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from db import get_db, SessionLog, FailureLog
from services.stt import VADState, transcribe_async
from services.llm import stream_chat, sentence_stream, contains_fallback
from services.tts import synthesize_async
from services.rag import get_rag
from services.memory import get_context, get_recurring_errors, summarize_session, store_summary
from prompts.sensei import build_system_prompt
from config import settings

router = APIRouter(tags=["voice"])

SILENCE_TIMEOUT_S = 15.0  # productive struggle: >15s silence = non-productive


@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()

    # Create session log entry
    session = SessionLog(
        started_at=datetime.utcnow(),
        grammar_level=settings.default_grammar_level,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    vad = VADState()
    conversation: list[dict] = []
    turn_count = 0
    productive_turns = 0
    tone_mode = "textbook"
    grammar_level = settings.default_grammar_level
    task = "free_conversation"

    async def send_json(payload: dict):
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

    async def tts_worker(sentence_queue: asyncio.Queue):
        """Pull sentences from the queue and synthesize, sending WAV chunks back."""
        while True:
            sentence = await sentence_queue.get()
            if sentence is None:  # Sentinel value
                break
            try:
                wav_bytes = await synthesize_async(sentence)
                if wav_bytes:
                    await websocket.send_bytes(wav_bytes)
            except Exception as e:
                await send_json({"type": "error", "text": str(e)})
            finally:
                sentence_queue.task_done()

    try:
        while True:
            # Receive binary PCM or text control frames
            try:
                data = await asyncio.wait_for(websocket.receive(), timeout=SILENCE_TIMEOUT_S + 5)
            except asyncio.TimeoutError:
                continue

            if "text" in data:
                # Control message from frontend
                try:
                    ctrl = json.loads(data["text"])
                    if ctrl.get("type") == "config":
                        tone_mode = ctrl.get("tone_mode", tone_mode)
                        grammar_level = ctrl.get("grammar_level", grammar_level)
                        task = ctrl.get("task", task)
                except json.JSONDecodeError:
                    pass
                continue

            if "bytes" not in data:
                continue

            pcm_chunk = data["bytes"]

            # ── VAD ─────────────────────────────────────────────────────────
            t_vad_start = time.perf_counter()
            speech_bytes = vad.feed(pcm_chunk)
            t_vad_end = time.perf_counter()

            if speech_bytes is None:
                continue  # Speech not yet complete

            vad_ms = (t_vad_end - t_vad_start) * 1000

            # ── STT ─────────────────────────────────────────────────────────
            t_stt_start = time.perf_counter()
            transcript, confidence = await transcribe_async(speech_bytes)
            t_stt_end = time.perf_counter()
            stt_ms = (t_stt_end - t_stt_start) * 1000

            if not transcript.strip():
                continue

            await send_json({"type": "transcript", "text": transcript})
            turn_count += 1

            # Detect repeat requests (non-productive turn)
            is_productive = "もう一度" not in transcript

            # ── RAG + Prompt ─────────────────────────────────────────────────
            rag = get_rag()
            rag_chunks = rag.query_grammar(transcript, grammar_level)
            error_log = get_recurring_errors(db)
            session_memory = await get_context()

            system_prompt = build_system_prompt(
                rag_chunks=rag_chunks,
                tone_mode=tone_mode,
                error_log=error_log,
                task=task,
                session_memory=session_memory,
            )

            conversation.append({"role": "user", "content": transcript})

            # ── LLM + TTS Pipeline ───────────────────────────────────────────
            sentence_queue: asyncio.Queue = asyncio.Queue()
            tts_task = asyncio.create_task(tts_worker(sentence_queue))

            await send_json({"type": "tts_start"})

            t_llm_start = time.perf_counter()
            first_token = True
            llm_ttft_ms = 0.0
            full_response: list[str] = []

            async def feed_sentences():
                nonlocal first_token, llm_ttft_ms
                token_gen = stream_chat(conversation, system_prompt)
                async for sentence in sentence_stream(token_gen):
                    if first_token:
                        llm_ttft_ms = (time.perf_counter() - t_llm_start) * 1000
                        first_token = False
                    full_response.append(sentence)
                    await sentence_queue.put(sentence)
                await sentence_queue.put(None)  # Sentinel

            t_tts_start = time.perf_counter()
            await feed_sentences()
            await tts_task
            t_tts_end = time.perf_counter()
            tts_ms = (t_tts_end - t_tts_start) * 1000

            await send_json({"type": "tts_end"})

            response_text = "".join(full_response)
            conversation.append({"role": "assistant", "content": response_text})

            # ── Productive struggle tracking ──────────────────────────────────
            if is_productive and not contains_fallback(response_text):
                productive_turns += 1

            # Log low-confidence transcriptions
            if confidence < -1.0:  # avg_logprob threshold
                log = FailureLog(
                    session_id=session.id,
                    pattern="low_confidence_transcription",
                    whisper_confidence=confidence,
                )
                db.add(log)
                db.commit()

            # ── Latency report ───────────────────────────────────────────────
            await send_json({
                "type": "latency",
                "data": {
                    "vad_ms": round(vad_ms, 1),
                    "stt_ms": round(stt_ms, 1),
                    "llm_ttft_ms": round(llm_ttft_ms, 1),
                    "tts_ms": round(tts_ms, 1),
                    "total_ms": round(vad_ms + stt_ms + llm_ttft_ms + tts_ms, 1),
                },
            })

            vad.reset()

    except WebSocketDisconnect:
        pass
    finally:
        # ── Session close — persist metrics and memory ───────────────────────
        ended = datetime.utcnow()
        duration_s = (ended - session.started_at).total_seconds()

        session.ended_at = ended
        session.turn_count = turn_count
        session.productive_turns = productive_turns
        session.duration_s = duration_s
        session.grammar_level = grammar_level
        session.tone_mode = tone_mode
        db.commit()

        # Summarize and store session memory in background
        if conversation:
            summary = await summarize_session(conversation)
            await store_summary(str(session.id), summary)
