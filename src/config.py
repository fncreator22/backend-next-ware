import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Server configs
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    RELOAD: bool = True
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]

    # Database configs
    MONGODB_URL: str = "mongodb://localhost:27017"
    DB_NAME: str = "wareops_erp_db"

    # Security secrets
    JWT_SECRET: str = "super_secret_cryptographic_key_replace_in_production_32_bytes_min"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Redis config
    REDIS_URL: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Global settings singleton
settings = Settings()
