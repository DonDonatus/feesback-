from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    NODE_TYPE: Literal["local", "cloud"] = "local"
    DATABASE_URL: str = "sqlite:///./data/local.db"
    CORS_ORIGINS: str = "*"
    
    # Cloud sync settings
    SYNC_REMOTE_URL: str = "http://localhost:8001"
    SYNC_AUTH_TOKEN: str = "secret-sync-token-12345"
    
    # Hubtel payment settings
    HUBTEL_CLIENT_ID: str = ""
    HUBTEL_CLIENT_SECRET: str = ""
    HUBTEL_MERCHANT_ACCOUNT_NUMBER: str = ""
    HUBTEL_CALLBACK_URL: str = "http://localhost:8000/payments/hubtel/callback"
    HUBTEL_RETURN_URL: str = "http://localhost:8000/docs"
    HUBTEL_CANCELLATION_URL: str = "http://localhost:8000/docs"
    HUBTEL_SANDBOX: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
