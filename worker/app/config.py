from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    node_agent_token: str = "local-node-agent-token"
    worker_name: str = "local-worker"
    worker_public_base_url: str = "http://worker:9000"
    worker_data_dir: Path = Path("/var/lib/adbothost-worker")
    worker_max_containers: int = 20
    worker_enforce_storage_opt: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
settings.worker_data_dir.mkdir(parents=True, exist_ok=True)
