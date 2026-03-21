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

    # 稳定性/限流
    queue_file: str = Field("/opt/memL/data/pending_writes.jsonl", alias="MEML_QUEUE_FILE")
    idemp_file: str = Field("/opt/memL/data/idempotency.json", alias="MEML_IDEMP_FILE")
    tenant_max_memories: int = Field(50000, alias="MEML_TENANT_MAX_MEMORIES")
    tenant_write_rate_per_min: int = Field(120, alias="MEML_TENANT_WRITE_RATE_PER_MIN")
    audit_log_file: str = Field("/opt/memL/data/audit.log", alias="MEML_AUDIT_LOG_FILE")
    importance_longterm_threshold: float = Field(0.75, alias="MEML_IMPORTANCE_LONGTERM_THRESHOLD")

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
