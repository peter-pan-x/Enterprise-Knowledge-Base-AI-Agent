import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Enterprise Knowledge Agent")
    app_env: str = os.getenv("APP_ENV", "development")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "deepseek-chat")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "800"))
    rag_chunk_size: int = int(os.getenv("RAG_CHUNK_SIZE", "700"))
    rag_chunk_overlap: int = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "4"))
    rag_min_score: float = float(os.getenv("RAG_MIN_SCORE", "0.12"))
    embedding_dimension: int = int(os.getenv("EMBEDDING_DIMENSION", "384"))


settings = Settings()
