from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Mode
    ENV: str = "development"
    DEBUG: bool = True

    # FastAPI Server Configuration
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]

    # PostgreSQL Connection Parameters
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "marketeval"
    
    # Fully qualified Async PostgreSQL DSN
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/marketeval"

    # Model & Vector Settings
    MODEL_NAME: str = "VinAI/phobert-base"
    VECTOR_DIMENSION: int = 768

    # Telegram Webhook
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()