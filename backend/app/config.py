from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at the project root (one level above backend/).
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://faceplant:faceplant@localhost:5433/faceplant"
    frontend_url: str = "http://localhost:5174"

    media_root: str = str(Path(__file__).resolve().parents[1] / "uploads")
    max_avatar_mb: float = 5.0

    admin_api_key: str
    anthropic_api_key: str = ""
    default_bot_model: str = "claude-haiku-4-5"

    short_reaction_window_minutes: int = 5
    long_reaction_window_min_minutes: int = 15
    long_reaction_window_max_minutes: int = 180

    short_wave_size_min: int = 3
    short_wave_size_max: int = 5
    long_wave_size_min: int = 3
    long_wave_size_max: int = 5


settings = Settings()
