from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret: str = "change-me-app-secret"
    jwt_secret: str = "change-me-jwt-secret"
    admin_secret: str = "change-me-admin-secret"
    admin_username: str = "admin"
    admin_password: str = "change-me-admin-password"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    admin_email: str = "admin@adbothost.local"
    public_base_url: str = "http://localhost"
    api_root_path: str = ""

    database_url: str = "sqlite:///./adbothost.db"
    backend_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:5173"
    upload_dir: Path = Path("./uploads")
    scheduler_enabled: bool = True

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    default_node_agent_token: str = "local-node-agent-token"
    controller_signing_secret: str = "local-controller-signing-secret"
    worker_name: str = "local-worker"
    worker_public_base_url: str = "http://worker:9000"
    worker_max_containers: int = 20

    ad_reward_credits: float = 1.0
    scan_max_file_mb: int = 25
    allow_negative_credits: bool = False

    manual_payment_enabled: bool = True
    manual_payment_provider_name: str = "Binance Pay"
    manual_payment_receiver_id: str = ""
    manual_payment_instructions: str = "Send payment, then submit your Binance ID and TxID."
    manual_payment_currency: str = "USDT"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> List[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        if self.public_base_url not in origins:
            origins.append(self.public_base_url)
        return origins


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
