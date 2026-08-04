from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_root() -> Path:
    """Find the checked-in data directory in both monorepo and image layouts."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data"
        if (candidate / "demo").is_dir():
            return candidate
    return Path("/data")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../../.env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    database_url: str = Field(default="sqlite+aiosqlite:///./aletheia.db", repr=False)
    migration_database_url: str = Field(default="", repr=False)
    database_pool_size: int = Field(default=3, ge=1, le=10)
    database_max_overflow: int = Field(default=2, ge=0, le=10)
    environment: Literal["local", "test", "production"] = "production"
    data_root: Path = Field(default_factory=_default_data_root)
    web_origin: str = "http://localhost:3000"
    demo_mode: bool = True
    demo_inline_jobs: bool = True
    demo_reset_secret: str = ""
    upload_max_bytes: int = 2 * 1024 * 1024
    worker_poll_seconds: float = 1.0
    worker_lease_seconds: int = 60
    worker_max_attempts: int = 3
    guest_max_operations: int = Field(default=6, ge=2, le=20)
    guest_max_mutations: int = Field(default=30, ge=10, le=100)
    guest_session_ttl_hours: int = Field(default=168, ge=1, le=720)
    guest_retention_days: int = Field(default=30, ge=1, le=365)
    guest_cleanup_interval_hours: int = Field(default=24, ge=1, le=168)
    api_max_body_bytes: int = Field(default=64 * 1024, ge=4 * 1024, le=1024 * 1024)
    log_level: str = "INFO"
    openai_api_key: str = Field(default="", repr=False)
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5-mini"
    supabase_issuer: str = ""
    supabase_jwks_url: str = ""
    supabase_audience: str = "authenticated"
    api_origin_token: str = Field(default="", repr=False)

    @field_validator("database_url")
    @classmethod
    def normalize_async_database_url(cls, value: str) -> str:
        """Render-style Postgres URLs need SQLAlchemy's asyncpg dialect name."""
        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql+asyncpg://", 1)
        elif value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql+asyncpg://"):
            parsed = urlsplit(value)
            query = [
                ("ssl" if key == "sslmode" else key, item)
                for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            ]
            return urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
            )
        return value

    @field_validator("migration_database_url")
    @classmethod
    def normalize_migration_database_url(cls, value: str) -> str:
        """Alembic and the startup lock use a synchronous psycopg connection."""
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql+asyncpg://"):
            return value.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        return value

    @model_validator(mode="after")
    def validate_hosted_security(self) -> "Settings":
        if not self.hosted_mode:
            return self
        required = {
            "MIGRATION_DATABASE_URL": self.migration_database_url,
            "SUPABASE_ISSUER": self.supabase_issuer,
            "SUPABASE_JWKS_URL": self.supabase_jwks_url,
            "SUPABASE_AUDIENCE": self.supabase_audience,
            "API_ORIGIN_TOKEN": self.api_origin_token,
            "WEB_ORIGIN": self.web_origin,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Hosted mode requires: {', '.join(missing)}")
        if self.environment == "production":
            if self.supabase_audience != "authenticated":
                raise ValueError("Production SUPABASE_AUDIENCE must be authenticated")
            if len(self.api_origin_token) < 32:
                raise ValueError("Production API_ORIGIN_TOKEN must contain at least 32 characters")
            if self.database_url.startswith("sqlite"):
                raise ValueError("Production requires PostgreSQL")
            if not self.migration_database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Production MIGRATION_DATABASE_URL must use PostgreSQL/psycopg")
            issuer = urlsplit(self.supabase_issuer)
            jwks = urlsplit(self.supabase_jwks_url)
            web = urlsplit(self.web_origin)
            for name, parsed in {
                "SUPABASE_ISSUER": issuer,
                "SUPABASE_JWKS_URL": jwks,
                "WEB_ORIGIN": web,
            }.items():
                if (
                    parsed.scheme != "https"
                    or not parsed.hostname
                    or parsed.username
                    or parsed.password
                ):
                    raise ValueError(f"{name} must use an HTTPS URL without credentials")
            if web.path not in {"", "/"} or web.query or web.fragment:
                raise ValueError("WEB_ORIGIN must be an origin without a path, query, or fragment")
            expected_jwks = f"{self.supabase_issuer.rstrip('/')}/.well-known/jwks.json"
            if self.supabase_jwks_url != expected_jwks:
                raise ValueError("SUPABASE_JWKS_URL must belong to the configured issuer")
            runtime = urlsplit(self.database_url)
            migration = urlsplit(self.migration_database_url)
            if runtime.port != 5432 or migration.port != 5432:
                raise ValueError("Production database URLs must use Supavisor session port 5432")
            if dict(parse_qsl(runtime.query)).get("ssl") not in {
                "require",
                "verify-ca",
                "verify-full",
                "true",
            }:
                raise ValueError("DATABASE_URL must require TLS")
            if dict(parse_qsl(migration.query)).get("sslmode") not in {
                "require",
                "verify-ca",
                "verify-full",
            }:
                raise ValueError("MIGRATION_DATABASE_URL must require TLS")
        return self

    @property
    def hosted_mode(self) -> bool:
        """Authentication is bypassed only in explicitly selected local/test modes."""
        return self.environment == "production"

    @property
    def local_identity_enabled(self) -> bool:
        return self.environment in {"local", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
