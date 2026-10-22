import json
import os
from typing import List, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "CastTrace AI"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    HOST: str = "127.0.0.1"
    PORT: int = 8001
    LOG_LEVEL: str = "INFO"

    SECRET_KEY: str = "casttrace-dev-insecure-secret-key-change-in-production-32bytes-min"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    DATABASE_URL: str = "sqlite:///./casttrace.db"
    STORAGE_DIR: str = "./storage/evidence"
    MAX_UPLOAD_SIZE_BYTES: int = 10485760  # 10 MB

    ML_ARTIFACTS_DIR: str = "ml/artifacts"
    MODEL_METADATA_FILE: str = "model_metadata.json"
    WORKER_POLL_INTERVAL: float = 1.0

    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        elif isinstance(v, list):
            return v
        return []

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Fail safely in production if insecure defaults or unsafe configurations are detected."""
        if self.APP_ENV.lower() == "production":
            # 1. SECRET_KEY security check
            insecure_markers = [
                "casttrace-dev-insecure-secret-key-change-in-production-32bytes-min",
                "secret-key",
                "changeme",
                "insecure",
                "casttrace-dev",
            ]
            key_lower = self.SECRET_KEY.lower()
            if any(marker in key_lower for marker in insecure_markers):
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: A default or development SECRET_KEY "
                    "cannot be used in production environment. Configure a strong, random SECRET_KEY "
                    "(e.g., via `python -c \"import secrets; print(secrets.token_urlsafe(32))\"`)."
                )
            if len(self.SECRET_KEY) < 32:
                raise ValueError(
                    f"CRITICAL SECURITY CONFIGURATION ERROR: Production SECRET_KEY must be at least "
                    f"32 characters long (current length: {len(self.SECRET_KEY)})."
                )

            # 2. Debug mode check
            if self.APP_DEBUG:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: APP_DEBUG must be set to false in production "
                    "to prevent detailed stack trace disclosure."
                )

            # 3. CORS wildcard check
            if "*" in self.BACKEND_CORS_ORIGINS:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: BACKEND_CORS_ORIGINS must not contain wildcard '*' "
                    "in production environment when credentialed authentication is enabled."
                )

        return self


settings = Settings()
