"""
Modular system prompt builder for the Aki-Sensei persona.
Each slot is independently configurable; missing slots are omitted gracefully.
"""

from typing import Optional

PERSONA_BLOCK = """あなたは「アキ先生」です。あなたは忍耐強く、温かみのある日本語の先生です。
重要なルール:
- 絶対に英語に切り替えてはいけません。日本語のみで話してください。
- 学習者が間違えても、文の途中で訂正しないでください。
- 発話が終わった後に、自然な表現を「なるほど、普通は『…』と言いますよ」という形で優しく教えてください。
- 学習者のレベルに合わせた文法のみを使用してください。"""

TEXTBOOK_TONE_BLOCK = """【トーンモード: 教科書モード】
- ます形・です形のみを使用してください。
- 敬語を使ってください。
- スラングや略語は使わないでください。
- ゆっくり、はっきりと話してください。"""

ANIME_TONE_BLOCK = """【トーンモード: アニメカジュアルモード】
- だ・である形を使用してください。
- 短縮形を使ってください（「ている」→「てる」など）。
- 状況に応じて性差のある言葉遣いを使ってください。
- 自然な会話の流れを大切にしてください。"""

TASK_BLOCKS = {
    "free_conversation": """【タスク: 自由会話】
自然な会話を楽しんでください。学習者が話した内容に反応し、質問や感想を加えて会話を続けてください。""",

    "shadowing": """【タスク: シャドーイング】
短い文を一つずつ読み上げてください。学習者が繰り返した後、発音やイントネーションについて簡単なフィードバックをしてください。""",

    "drill": """【タスク: 語彙ドリル】
単語や表現を文脈の中で使い、学習者が理解しているか確認してください。例文を使って自然な使い方を示してください。""",

    "grammar_focus": """【タスク: 文法フォーカス】
一つの文法ポイントに集中してください。例文を3つ示し、学習者に練習させてください。間違いは発話後に優しく訂正してください。""",
}


def build_system_prompt(
    rag_chunks: Optional[list[str]] = None,
    tone_mode: str = "textbook",
    error_log: Optional[list[str]] = None,
    task: str = "free_conversation",
    session_memory: Optional[str] = None,
) -> str:
    blocks = [PERSONA_BLOCK]

    # Tone
    if tone_mode == "anime":
        blocks.append(ANIME_TONE_BLOCK)
    else:
        blocks.append(TEXTBOOK_TONE_BLOCK)

    # Level / RAG grammar constraints
    if rag_chunks:
        chunk_text = "\n".join(f"- {c}" for c in rag_chunks)
        blocks.append(
            f"【文法レベル制約】\n以下の文法ポイントのみを使用してください:\n{chunk_text}"
        )

    # Session memory
    if session_memory:
        blocks.append(
            f"【前回のセッション記録】\n{session_memory}"
        )

    # Known errors
    if error_log:
        errors = "\n".join(f"- {e}" for e in error_log[:3])
        blocks.append(
            f"【学習者の既知の誤りパターン】\n以下の点に特に注意してフィードバックしてください:\n{errors}"
        )

    # Task
    task_block = TASK_BLOCKS.get(task, TASK_BLOCKS["free_conversation"])
    blocks.append(task_block)

    return "\n\n".join(blocks)
