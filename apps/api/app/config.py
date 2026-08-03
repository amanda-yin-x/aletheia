from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_root() -> Path:
    """Find the checked-in data directory in both monorepo and image layouts."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data"
        if (candidate / "demo").is_dir():
            return candidate
    return Path("/data")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./aletheia.db"
    data_root: Path = Field(default_factory=_default_data_root)
    web_origin: str = "http://localhost:3000"
    demo_mode: bool = True
    demo_inline_jobs: bool = True
    demo_reset_secret: str = ""
    upload_max_bytes: int = 2 * 1024 * 1024
    worker_poll_seconds: float = 1.0
    worker_lease_seconds: int = 60
    log_level: str = "INFO"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5-mini"

    @field_validator("database_url")
    @classmethod
    def normalize_async_database_url(cls, value: str) -> str:
        """Render-style Postgres URLs need SQLAlchemy's asyncpg dialect name."""
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
