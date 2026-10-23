import json
import os
from typing import List, Optional, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
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

    DATABASE_URL: str
    TEST_DATABASE_URL: str
    STORAGE_DIR: str = "./storage/evidence"
    MAX_UPLOAD_SIZE_BYTES: int = 10485760  # 10 MB

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v: Optional[str]) -> str:
        if not v or not str(v).strip():
            raise ValueError(
                "CONFIGURATION ERROR: DATABASE_URL is required and cannot be empty. "
                "CastTrace AI has standardized exclusively on PostgreSQL. Please configure a valid PostgreSQL connection string "
                "(e.g., postgresql+psycopg2://postgres:password@127.0.0.1:5432/casttrace_dev)."
            )
        v_str = str(v).strip()
        v_lower = v_str.lower()
        if v_lower.startswith("sqlite"):
            raise ValueError(
                "CONFIGURATION ERROR: SQLite is not supported. CastTrace AI has standardized exclusively on PostgreSQL. "
                "Please configure a valid PostgreSQL connection string (e.g., postgresql+psycopg2://<user>:<password>@<host>:<port>/<dbname>)."
            )
        if not (v_lower.startswith("postgresql://") or v_lower.startswith("postgresql+")):
            raise ValueError(
                f"CONFIGURATION ERROR: DATABASE_URL must be a PostgreSQL connection string (postgresql:// or postgresql+...), "
                f"got scheme: {v_str.split('://')[0] if '://' in v_str else v_str}"
            )
        return v_str

    @field_validator("TEST_DATABASE_URL", mode="before")
    @classmethod
    def validate_test_database_url(cls, v: Optional[str]) -> str:
        if not v or not str(v).strip():
            raise ValueError(
                "CONFIGURATION ERROR: TEST_DATABASE_URL is required and cannot be empty. "
                "CastTrace AI requires a dedicated, isolated PostgreSQL test database to prevent test pollution or data corruption "
                "(e.g., postgresql+psycopg2://postgres:password@127.0.0.1:5432/casttrace_test)."
            )
        v_str = str(v).strip()
        v_lower = v_str.lower()
        if v_lower.startswith("sqlite"):
            raise ValueError(
                "CONFIGURATION ERROR: SQLite is not supported for testing. CastTrace AI has standardized exclusively on PostgreSQL. "
                "Please configure an isolated PostgreSQL test database (e.g., postgresql+psycopg2://<user>:<password>@<host>:<port>/casttrace_test)."
            )
        if not (v_lower.startswith("postgresql://") or v_lower.startswith("postgresql+")):
            raise ValueError(
                f"CONFIGURATION ERROR: TEST_DATABASE_URL must be a PostgreSQL connection string (postgresql:// or postgresql+...), "
                f"got scheme: {v_str.split('://')[0] if '://' in v_str else v_str}"
            )
        return v_str

    ML_ARTIFACTS_DIR: str = "ml/artifacts"
    MODEL_METADATA_FILE: str = "model_metadata.json"
    WORKER_POLL_INTERVAL: float = 1.0

    # Generative AI (Gemini)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-flash-lite-latest"

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
