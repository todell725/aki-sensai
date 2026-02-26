# アキ先生 — Local Anime Fluency Engine

A privacy-first, locally-running Japanese fluency engine. All computation runs on your machine — your vocabulary struggles, pronunciation attempts, and learning history never leave your device.

## Architecture

```
Browser (Next.js PWA)
  ↕ WebSocket (PCM audio / WAV chunks)
FastAPI Backend
  ├── Silero-VAD   → end-of-speech detection (~50ms)
  ├── Faster-Whisper → transcription (~400ms GPU / ~1s CPU)
  ├── Ollama (Qwen3-8B) → LLM response streaming
  ├── ChromaDB     → textbook RAG + vocab + session memory
  ├── Piper TTS    → Japanese speech synthesis
  └── SQLite       → SRS cards, session logs, failure log
```

**Target latency:** < 2 seconds end-of-speech → first audio byte.

## Quick Start

### 1. Clone and configure

```bash
git clone <repo>
cd aki-sensai
cp .env.example .env
# Edit .env as needed
```

### 2. Pull the Piper model

```bash
mkdir -p models
# Download from https://github.com/rhasspy/piper/releases
# Place ja_JP-kana-medium.onnx in ./models/
```

### 3. Start all services

```bash
docker compose up
```

Then pull the LLM:

```bash
docker compose exec ollama ollama pull qwen3:8b
```

Open http://localhost:3000 in your browser.

---

## Development Setup (without Docker)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create data directories
mkdir -p /data /models

uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Ingesting Content

### Textbook PDFs (for level-locked grammar)

```bash
cd backend
python ../scripts/ingest_textbook.py --pdf /path/to/minna_no_nihongo.pdf --level N5
```

### Anime subtitle files (ASS/SRT)

```bash
python scripts/ingest_subtitles.py \
  --file ep01.ass ep02.ass ep03.ass \
  --show "Demon Slayer"
```

This outputs a **Show ID**. Use it in the app under Drills and Shadowing.

### JMdict vocabulary database (optional, adds JLPT levels to subtitle vocab)

```bash
python scripts/seed_jmdict.py --download
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `WS` | `/ws/voice` | Real-time voice conversation |
| `POST` | `/chat` | Streaming text conversation |
| `POST` | `/speak` | Text → WAV synthesis |
| `POST` | `/subtitles/upload` | Upload ASS/SRT subtitle file |
| `GET` | `/subtitles/{id}/vocab` | Frequency-ranked vocabulary |
| `GET` | `/drills/due` | Due SRS cards |
| `POST` | `/drills/{id}/review` | Submit SRS card review |
| `GET` | `/drills/stats` | SRS statistics |
| `POST` | `/pitch/analyze` | Pitch accent contour |
| `GET` | `/metrics` | Session metrics for dashboard |
| `GET` | `/health` | Service health check |

---

## Daily 15-Minute Session Structure

| Time | Activity |
|------|----------|
| 0:00–2:00 | SRS Review (due cards, max 10) |
| 2:00–5:00 | Shadowing drill (3 subtitle lines) |
| 5:00–12:00 | Free voice conversation |
| 12:00–14:00 | Grammar focus (one point from conversation) |
| 14:00–15:00 | Log review |

---

## Success Metrics

| Metric | Target | Location |
|--------|--------|----------|
| Voice latency | < 2 seconds | Chat page latency breakdown |
| Productive struggle ratio | > 60% | Dashboard |
| SRS accuracy | > 85% | Dashboard → SRS stats |
| Pitch accuracy | > 50% | Shadowing page |
| Daily immersion | 15 min/day | Dashboard → session log |

---

## Recommended Shows by Difficulty

| Show | Level | Notes |
|------|-------|-------|
| ドラえもん (Doraemon) | N5–N4 | Clear speech, child-addressed, repetitive |
| ポケモン (Pokémon) | N4–N3 | Action vocab, predictable patterns |
| 千と千尋の神隠し (Spirited Away) | N3 | Diverse registers, rich vocab |
| 鬼滅の刃 (Demon Slayer) | N3–N2 | High-frequency action/emotion vocab |
| シュタインズ・ゲート (Steins;Gate) | N2–N1 | Science jargon, otaku register |

---

## Dependency Reference

| Package | Purpose |
|---------|---------|
| `faster-whisper` | GPU-optimized Japanese STT |
| `silero-vad` | End-of-speech detection |
| `chromadb` | Vector store (RAG + memory) |
| `sentence-transformers` | Multilingual embeddings |
| `pysubs2` | ASS/SRT subtitle parsing |
| `fugashi` + `ipadic` | Japanese morphological analysis |
| `pyopenjtalk` | Pitch accent annotation |
| `librosa` | Audio pitch contour extraction |
| `pdfplumber` | Textbook PDF extraction |
| `ollama` | Local LLM client (Qwen3-8B) |
