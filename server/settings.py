from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings come from PLPR_* environment variables (or a .env file)."""

    model_config = SettingsConfigDict(env_prefix="PLPR_", env_file=".env", extra="ignore", protected_namespaces=())

    database_url: str = "sqlite:///./data/plpr.db"
    data_dir: Path = Path("./data")  # plate crops go to <data_dir>/crops
    model_dir: Path | None = None  # default: plpr's model/onnx
    retention_days: int = 90  # 0 keeps everything
    admin_token: str | None = None  # bootstrap admin key, upserted at startup
    max_upload_mb: float = 8.0
    plate_conf: float = 0.5
    char_conf: float = 0.5
    review_agreement: float = 0.8  # entries below either threshold land in the review queue
    review_conf: float = 0.6
    cors_origins: list[str] = []  # JSON list, e.g. ["http://localhost:5173"]
