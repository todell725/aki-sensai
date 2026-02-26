"""
ChromaDB RAG service.
Three collections:
  - textbook_chunks: grammar rules and example sentences from ingested PDFs
  - vocabulary: word entries with JLPT level and frequency metadata
  - user_memory: session summaries for long-term memory injection
"""

import uuid
from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from config import settings

LEVEL_ORDER = {"N5": 0, "N4": 1, "N3": 2, "N2": 3, "N1": 4}

_embedding_model: Optional[SentenceTransformer] = None
_chroma_client: Optional[chromadb.Client] = None


def _get_client() -> chromadb.Client:
    global _chroma_client
    if _chroma_client is None:
        if settings.chroma_host:
            _chroma_client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
            )
        else:
            _chroma_client = chromadb.PersistentClient(path=settings.chroma_path)
    return _chroma_client


def _get_embedder() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            "paraphrase-multilingual-MiniLM-L12-v2"
        )
    return _embedding_model


def _embed(texts: list[str]) -> list[list[float]]:
    return _get_embedder().encode(texts, normalize_embeddings=True).tolist()


class RAGService:
    def __init__(self):
        client = _get_client()
        self._textbook = client.get_or_create_collection(
            name="textbook_chunks",
            metadata={"hnsw:space": "cosine"},
        )
        self._vocabulary = client.get_or_create_collection(
            name="vocabulary",
            metadata={"hnsw:space": "cosine"},
        )
        self._memory = client.get_or_create_collection(
            name="user_memory",
            metadata={"hnsw:space": "cosine"},
        )

    # ── Textbook ────────────────────────────────────────────────────────────

    def add_textbook_chunk(
        self,
        text: str,
        level: str = "N5",
        chapter: str = "",
        source: str = "",
        chunk_id: Optional[str] = None,
    ) -> None:
        doc_id = chunk_id or str(uuid.uuid4())
        embedding = _embed([text])[0]
        self._textbook.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{"level": level, "chapter": chapter, "source": source}],
        )

    def query_grammar(
        self,
        user_text: str,
        grammar_level: str = "N5",
        n_results: int = 3,
    ) -> list[str]:
        """Return top-N grammar chunks at or below the user's level."""
        if self._textbook.count() == 0:
            return []

        level_value = LEVEL_ORDER.get(grammar_level, 0)
        allowed_levels = [k for k, v in LEVEL_ORDER.items() if v <= level_value]

        embedding = _embed([user_text])[0]

        results = self._textbook.query(
            query_embeddings=[embedding],
            n_results=min(n_results * 3, max(self._textbook.count(), 1)),
            where={"level": {"$in": allowed_levels}} if allowed_levels else None,
        )

        docs = results.get("documents", [[]])[0]
        return docs[:n_results]

    def add_textbook_chunks_batch(self, chunks: list[dict]) -> None:
        """Batch insert: each dict has keys text, level, chapter, source."""
        if not chunks:
            return
        texts = [c["text"] for c in chunks]
        embeddings = _embed(texts)
        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [
            {
                "level": c.get("level", "N5"),
                "chapter": c.get("chapter", ""),
                "source": c.get("source", ""),
            }
            for c in chunks
        ]
        self._textbook.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

    # ── Vocabulary ──────────────────────────────────────────────────────────

    def add_vocab(
        self,
        word: str,
        reading: str = "",
        meaning: str = "",
        jlpt_level: str = "",
        frequency: int = 1,
        show_id: str = "",
    ) -> None:
        doc_text = f"{word} {reading} {meaning}"
        embedding = _embed([doc_text])[0]
        doc_id = f"vocab_{word}_{show_id}" if show_id else f"vocab_{word}"
        self._vocabulary.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[doc_text],
            metadatas=[{
                "word": word,
                "reading": reading,
                "meaning": meaning,
                "jlpt_level": jlpt_level,
                "frequency": frequency,
                "show_id": show_id,
            }],
        )

    # ── Session Memory ──────────────────────────────────────────────────────

    def add_memory(self, session_id: str, summary: str) -> None:
        embedding = _embed([summary])[0]
        self._memory.upsert(
            ids=[f"session_{session_id}"],
            embeddings=[embedding],
            documents=[summary],
            metadatas=[{"session_id": session_id}],
        )

    def get_recent_sessions(self, n: int = 5) -> list[str]:
        """Retrieve most recent session summaries (by insertion order approximation)."""
        if self._memory.count() == 0:
            return []
        results = self._memory.get(limit=n, include=["documents"])
        return results.get("documents", [])


_rag_service: Optional[RAGService] = None


def get_rag() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
