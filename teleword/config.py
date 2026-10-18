from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables or a local `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: SecretStr = SecretStr("")
    admin_id: int = 0

    database_url: str = "sqlite+aiosqlite:///./data/teleword.db"
    # Empty -> in-memory FSM storage (state is lost on restart).
    redis_url: str = ""

    dictionary_api_url: str = "https://api.dictionaryapi.dev/api/v2/entries/en/"
    # Shown to users in the /api instructions.
    api_public_url: str = "http://localhost:8080"

    timezone: str = "UTC"
    log_level: str = "INFO"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def today(self) -> date:
        return self.now().date()


@lru_cache
def get_settings() -> Settings:
    return Settings()
