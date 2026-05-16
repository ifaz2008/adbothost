from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_control_bot_token: str = ""
    telegram_backend_url: str = "http://backend:8000"
    public_base_url: str = "http://localhost"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
