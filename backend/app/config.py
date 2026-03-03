from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # API Keys
    GROQ_API_KEY: str
    SERPAPI_API_KEY: str
    GITHUB_TOKEN: Optional[str] = None   # Optional — unlocks 5000 req/hr vs 60

    # JWT Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # App
    DEBUG: bool = True

    # v2 Settings
    CONFIDENCE_THRESHOLD: int = 70          # Minimum confidence to skip web search
    SEMGREP_ENABLED: bool = False           # Enable Semgrep for static analysis (requires semgrep CLI)
    MAX_AST_FILES: int = 800                # Cap file count for AST scanning
    MAX_AST_FILE_SIZE_KB: int = 200         # Skip files larger than this (KB)
    DEFAULT_PERSONA: str = "SOLO_DEV"       # Fallback persona if routing fails

    class Config:
        env_file = ".env"


settings = Settings()