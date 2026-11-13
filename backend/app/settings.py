from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Look for .env at the project root (one level above backend/) *and* at CWD.
_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(_ROOT_ENV, ".env"), extra="ignore")

    postgres_user: str = "docs"
    postgres_password: str = "docs"
    postgres_db: str = "docs"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    jwt_secret: str = Field(default="change-me-to-a-long-random-string")
    jwt_alg: str = "HS256"
    session_ttl: int = 60 * 60 * 24 * 7

    allowed_origins: str = "http://localhost:5173"
    env: str = "dev"  # "dev" or "prod"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
