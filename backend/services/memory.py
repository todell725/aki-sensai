"""
Session memory service.

At session end: summarize the conversation turns using the LLM and store in ChromaDB.
At session start: retrieve the last N session summaries and inject into the system prompt.
"""

import asyncio
from typing import Optional

from services.rag import get_rag
from services.llm import get_single_response

SUMMARIZE_PROMPT = """以下の会話セッションを日本語で簡潔に要約してください。
以下の点を含めてください:
- 話したトピック
- 学習者が犯した誤り（もしあれば）
- 使用した語彙や文法

会話:
{conversation}

要約（3〜5文で）:"""


async def summarize_session(turns: list[dict]) -> str:
    """Use LLM to generate a short session summary."""
    if not turns:
        return ""

    conversation_text = "\n".join(
        f"{'学習者' if t['role'] == 'user' else 'アキ先生'}: {t['content']}"
        for t in turns
    )

    messages = [{"role": "user", "content": SUMMARIZE_PROMPT.format(conversation=conversation_text)}]
    try:
        summary = await get_single_response(
            messages,
            system_prompt="あなたは会話セッションを要約するAIです。日本語で簡潔に答えてください。",
        )
        return summary.strip()
    except Exception:
        return ""


async def store_summary(session_id: str, summary: str) -> None:
    """Persist session summary to ChromaDB user_memory collection."""
    if not summary:
        return
    rag = get_rag()
    await asyncio.to_thread(rag.add_memory, session_id, summary)


async def get_context(n_sessions: int = 5) -> str:
    """
    Retrieve the last N session summaries and format them for system prompt injection.
    Returns empty string if no prior sessions exist.
    """
    rag = get_rag()
    summaries = await asyncio.to_thread(rag.get_recent_sessions, n_sessions)
    if not summaries:
        return ""
    return "\n".join(f"- {s}" for s in summaries)


def get_recurring_errors(db_session, n: int = 3) -> list[str]:
    """
    Query the SQLite failure_log for top recurring patterns.
    Returns a list of pattern strings for system prompt injection.
    """
    from sqlalchemy import func
    from db import FailureLog

    results = (
        db_session.query(
            FailureLog.pattern,
            func.count(FailureLog.pattern).label("cnt"),
        )
        .filter(FailureLog.pattern.isnot(None))
        .group_by(FailureLog.pattern)
        .order_by(func.count(FailureLog.pattern).desc())
        .limit(n)
        .all()
    )
    return [row.pattern for row in results if row.pattern]
