from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Configuration centralisée de l’API."""

    app_name: str = "Chat Auto n8n"
    sqlite_db_path: Path = PROJECT_ROOT / "chat.db"
    n8n_webhook_url: Optional[str] = None
    n8n_callback_token: Optional[str] = None
    request_timeout: float = 15.0
    frontend_origin: str = "http://localhost:5173"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_exp_minutes: int = 15
    refresh_token_exp_minutes: int = 60 * 24 * 7  # 1 semaine
    bcrypt_rounds: int = 12

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8")

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.sqlite_db_path}"

    @property
    def cors_allow_origins(self) -> list[str]:
        raw = self.frontend_origin
        return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

