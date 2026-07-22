from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ForgeAI"
    environment: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3002",
            "http://127.0.0.1:3002",
        ]
    )

    workspace_root: Path = Field(default_factory=lambda: Path.cwd())
    artifact_dir: Path = Field(default_factory=lambda: Path(".forgeai/artifacts"))

    database_url: str = "sqlite:///./.forgeai/forgeai.db"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "forgeai_repo_chunks"

    runner_mode: str = "inline"
    approval_mode: str = "required"
    enable_cloud_plugins: bool = False

    default_reasoning_model: str = "gpt-5.6-sol"
    default_balanced_model: str = "gpt-5.6-terra"
    default_economy_model: str = "gpt-5.6-luna"
    embedding_provider: str = "local-hash"
    embedding_dimensions: int = 384

    otel_service_name: str = "forgeai-api"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def ensure_runtime_dirs(self) -> None:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite:///"):
            sqlite_path = Path(self.database_url.removeprefix("sqlite:///"))
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_runtime_dirs()
    return settings
