from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import yaml


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = Field("0.0.0.0", alias="MEML_HOST")
    port: int = Field(8000, alias="MEML_PORT")
    log_level: str = Field("INFO", alias="MEML_LOG_LEVEL")
    data_dir: str = Field("/opt/memL/data/chromadb", alias="MEML_DATA_DIR")
    tenants_file: str = Field("/opt/memL/tenants.yaml", alias="MEML_TENANTS_FILE")
    admin_token: str = Field("", alias="MEML_ADMIN_TOKEN")

    # 检索/去重
    dedup_enabled: bool = Field(True, alias="MEML_DEDUP_ENABLED")
    dedup_threshold: float = Field(0.92, alias="MEML_DEDUP_THRESHOLD")
    hybrid_alpha: float = Field(0.7, alias="MEML_HYBRID_ALPHA")

    # embedding
    embed_api_url: str = Field(..., alias="MEML_EMBED_API_URL")
    embed_api_key: str = Field(..., alias="MEML_EMBED_API_KEY")
    embed_model: str = Field(..., alias="MEML_EMBED_MODEL")
    embed_timeout_sec: float = Field(8.0, alias="MEML_EMBED_TIMEOUT_SEC")
    embed_max_retries: int = Field(2, alias="MEML_EMBED_MAX_RETRIES")
    embed_max_concurrency: int = Field(16, alias="MEML_EMBED_MAX_CONCURRENCY")


settings = Settings()


def load_tenants(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("tenants", {})


def save_tenants(path: str, tenants: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"tenants": tenants}, f, allow_unicode=True, sort_keys=True)
