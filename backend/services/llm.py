"""
Ollama LLM service with token streaming and sentence-boundary buffering for TTS.
"""

import asyncio
from typing import AsyncGenerator, Optional
import ollama

from config import settings

SENTENCE_TERMINATORS = {"。", "！", "？", "!", "?", "\n"}
FALLBACK_PHRASES = {"もう一度", "わかりません", "理解できません"}


async def stream_chat(
    messages: list[dict],
    system_prompt: str,
) -> AsyncGenerator[str, None]:
    """Yield raw tokens from Ollama streaming response."""
    client = ollama.AsyncClient(host=settings.ollama_host)
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    async for chunk in await client.chat(
        model=settings.ollama_model,
        messages=full_messages,
        stream=True,
    ):
        token = chunk["message"]["content"]
        if token:
            yield token


async def sentence_stream(
    token_gen: AsyncGenerator[str, None],
) -> AsyncGenerator[str, None]:
    """
    Buffer tokens from an async token stream and yield complete sentences
    at sentence boundaries (。！？\n). Used to feed the TTS queue so synthesis
    can start before the LLM finishes generating.
    """
    buffer = ""
    async for token in token_gen:
        buffer += token
        for terminator in SENTENCE_TERMINATORS:
            if terminator in buffer:
                # Split on first occurrence of any terminator
                idx = next(
                    (buffer.index(t) for t in SENTENCE_TERMINATORS if t in buffer),
                    None,
                )
                if idx is not None:
                    sentence = buffer[: idx + 1].strip()
                    buffer = buffer[idx + 1 :]
                    if sentence:
                        yield sentence
                break

    # Flush any remaining text
    if buffer.strip():
        yield buffer.strip()


def contains_fallback(text: str) -> bool:
    """Detect if the response is a fallback/repeat request."""
    return any(phrase in text for phrase in FALLBACK_PHRASES)


async def get_single_response(
    messages: list[dict],
    system_prompt: str,
) -> str:
    """Collect full LLM response as a string (for summarization tasks)."""
    result = []
    async for token in stream_chat(messages, system_prompt):
        result.append(token)
    return "".join(result)
