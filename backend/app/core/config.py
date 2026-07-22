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
    # Cosine scores below this point are commonly unrelated semantic-neighbour noise.
    # Tenants may tune it for their corpus through RAG_MIN_SCORE.
    rag_min_score: float = float(os.getenv("RAG_MIN_SCORE", "0.4"))
    embedding_dimension: int = int(os.getenv("EMBEDDING_DIMENSION", "384"))
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "local_hash")
    embedding_base_url: str = os.getenv("EMBEDDING_BASE_URL", "")
    embedding_api_key: str = os.getenv("EMBEDDING_API_KEY", "")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    auth_secret: str = os.getenv("AUTH_SECRET", "development-only-change-me")
    auth_token_hours: int = int(os.getenv("AUTH_TOKEN_HOURS", "12"))
    initial_admin_username: str = os.getenv("INITIAL_ADMIN_USERNAME", "admin")
    initial_admin_password: str = os.getenv("INITIAL_ADMIN_PASSWORD", "admin123")
    initial_user_username: str = os.getenv("INITIAL_USER_USERNAME", "user")
    initial_user_password: str = os.getenv("INITIAL_USER_PASSWORD", "user123")
    api_rate_limit_per_minute: int = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "120"))


settings = Settings()
