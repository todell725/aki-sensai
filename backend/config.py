import torch
from pydantic_settings import BaseSettings
from pydantic import Field


def _default_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def _default_compute_type() -> str:
    return "float16" if torch.cuda.is_available() else "int8"


class Settings(BaseSettings):
    # Ollama / LLM
    ollama_host: str = Field(default="http://localhost:11434", env="OLLAMA_HOST")
    ollama_model: str = Field(default="qwen3:8b", env="OLLAMA_MODEL")

    # Whisper / STT
    whisper_model: str = Field(default="large-v3", env="WHISPER_MODEL")
    whisper_device: str = Field(default_factory=_default_device, env="WHISPER_DEVICE")
    whisper_compute_type: str = Field(default_factory=_default_compute_type, env="WHISPER_COMPUTE_TYPE")
    whisper_beam_size: int = Field(default=1, env="WHISPER_BEAM_SIZE")

    # Piper / TTS
    piper_model_path: str = Field(default="/models/ja_JP-kana-medium.onnx", env="PIPER_MODEL_PATH")
    piper_binary: str = Field(default="piper", env="PIPER_BINARY")

    # ChromaDB / RAG
    chroma_path: str = Field(default="/data/chroma", env="CHROMA_PATH")
    chroma_host: str = Field(default="", env="CHROMA_HOST")  # empty = local PersistentClient
    chroma_port: int = Field(default=8001, env="CHROMA_PORT")

    # SQLite
    sqlite_path: str = Field(default="/data/aki.db", env="SQLITE_PATH")

    # Learning settings
    default_grammar_level: str = Field(default="N5", env="DEFAULT_GRAMMAR_LEVEL")

    # VAD
    vad_threshold: float = Field(default=0.5, env="VAD_THRESHOLD")
    vad_silence_ms: int = Field(default=300, env="VAD_SILENCE_MS")

    # Latency targets (ms) — used in profiling logs
    target_vad_ms: int = 50
    target_stt_ms: int = 400
    target_llm_ttft_ms: int = 300
    target_tts_ms: int = 400

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
