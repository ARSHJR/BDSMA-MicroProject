from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    data_dir: Path = ROOT / "data" / "processed"
    model_dir: Path = ROOT / "data" / "models"
    # sqlite by default; set to a Supabase/Postgres URL (postgresql+psycopg2://...) to migrate
    database_url: str = f"sqlite:///{(ROOT / 'data' / 'app.db').as_posix()}"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")


settings = Settings()
