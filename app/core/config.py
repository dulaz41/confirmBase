from __future__ import annotations

import os
from typing import List, Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application settings
    APP_ENV: Literal["development", "production", "testing"] = "development"
    DEBUG: bool = False
    APP_NAME: str = "ConfirmBase Waitlist API"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # Database URLs
    # Async connection for FastAPI via asyncpg
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://waitlist_user:waitlist_secure_pass@db:5432/waitlist_db",
        description="Async PostgreSQL connection string",
    )
    # Sync connection for Alembic migrations and synchronous scripts
    SYNC_DATABASE_URL: Optional[str] = Field(
        default=None,
        description="Synchronous PostgreSQL connection string",
    )

    # CORS settings
    CORS_ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated list of allowed origins",
    )

    # Admin Authentication
    ADMIN_API_KEY: str = Field(
        default="development_secret_admin_api_key_do_not_use_in_production",
        description="Admin secret API key for protected export and management endpoints",
    )

    # Rate Limiting
    WAITLIST_RATE_LIMIT: int = Field(
        default=10,
        description="Max requests per window for waitlist registration",
    )
    WAITLIST_RATE_WINDOW_SECONDS: int = Field(
        default=60,
        description="Window size in seconds for waitlist registration",
    )
    ADMIN_RATE_LIMIT: int = Field(
        default=30,
        description="Max requests per window for admin endpoints",
    )
    ADMIN_RATE_WINDOW_SECONDS: int = Field(
        default=60,
        description="Window size in seconds for admin endpoints",
    )

    # Request Size Limit
    MAX_REQUEST_BODY_SIZE_BYTES: int = Field(
        default=10240,
        description="Maximum allowed request body size in bytes (10KB default)",
    )

    # Automated Backups
    BACKUP_SCHEDULE_HOUR_UTC: int = Field(
        default=2,
        description="Hour of day (UTC) for 24h backup schedule",
    )
    BACKUP_SCHEDULE_MINUTE_UTC: int = Field(
        default=0,
        description="Minute of hour (UTC) for 24h backup schedule",
    )
    BACKUP_DIRECTORY: str = Field(
        default="backups",
        description="Local directory for backups",
    )
    BACKUP_RETENTION_DAYS: int = Field(
        default=30,
        description="Number of days to retain backups before automated deletion",
    )
    BACKUP_STORAGE: Literal["local", "s3"] = Field(
        default="local",
        description="Storage destination for backups (local or s3)",
    )
    BACKUP_ENCRYPTION_KEY: Optional[str] = Field(
        default=None,
        description="Optional Fernet symmetric encryption key for backups",
    )

    # Optional S3 settings
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: Optional[str] = None
    S3_ENDPOINT_URL: Optional[str] = None

    # Email Service Configuration
    SEND_CONFIRMATION_EMAIL: bool = Field(
        default=True,
        description="Whether to dispatch confirmation emails upon new registration",
    )
    EMAIL_PROVIDER: Literal["console", "smtp", "resend", "sendgrid"] = Field(
        default="console",
        description="Active email delivery provider (console, smtp, resend, sendgrid)",
    )
    EMAIL_FROM_ADDRESS: str = Field(
        default="noreply@example.com",
        description="Sender email address",
    )
    EMAIL_FROM_NAME: str = Field(
        default="Waitlist Team",
        description="Sender display name",
    )
    EMAIL_SUBJECT: str = Field(
        default="You're on the ConfirmBase early list! 🎉",
        description="Subject for waitlist confirmation emails",
    )
    PRODUCT_NAME: str = Field(
        default="ConfirmBase",
        description="Product name rendered in email notifications",
    )
    COMPANY_NAME: str = Field(
        default="ConfirmBase Team",
        description="Company / organization name in footer",
    )

    # SMTP Configuration (Standard SMTP, AWS SES SMTP, Postmark, Gmail, Brevo)
    SMTP_HOST: str = Field(default="localhost", description="SMTP server hostname")
    SMTP_PORT: int = Field(default=587, description="SMTP port")
    SMTP_USER: Optional[str] = Field(default=None, description="SMTP authentication username")
    SMTP_PASSWORD: Optional[str] = Field(default=None, description="SMTP authentication password")
    SMTP_TLS: bool = Field(default=True, description="Enable STARTTLS encryption")
    SMTP_SSL: bool = Field(default=False, description="Enable SSL direct connection (e.g. port 465)")

    # Resend API Configuration
    RESEND_API_KEY: Optional[str] = Field(default=None, description="Resend API key")

    # SendGrid API Configuration
    SENDGRID_API_KEY: Optional[str] = Field(default=None, description="SendGrid API key")

    @property
    def cors_origins(self) -> List[str]:
        origins = [
            origin.strip()
            for origin in self.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]
        if self.APP_ENV == "production":
            # Forbid wildcard in production
            filtered = [o for o in origins if o != "*"]
            return filtered
        if "null" not in origins:
            origins.append("null")
        return origins

    @property
    def async_db_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
            url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return url

    @property
    def sync_db_url(self) -> str:
        url = self.SYNC_DATABASE_URL or self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        elif url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        elif url.startswith("sqlite+aiosqlite://"):
            url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)

        # In SQLAlchemy 2.1+, postgresql:// defaults to psycopg (v3).
        # Seamlessly adapt to whichever driver is installed (psycopg v3 or psycopg2 v2):
        if url.startswith("postgresql://"):
            try:
                import psycopg  # noqa: F401
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            except ImportError:
                try:
                    import psycopg2  # noqa: F401
                    url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
                except ImportError:
                    pass
        return url

    @field_validator("ADMIN_API_KEY")
    @classmethod
    def validate_admin_key(cls, v: str, info) -> str:
        # Check against trivial insecure values in production
        env = os.getenv("APP_ENV", "development")
        if env == "production" and (
            v == "change_this_to_a_secure_random_admin_key_in_production"
            or v == "replace_me"
            or len(v) < 16
        ):
            raise ValueError(
                "In production, ADMIN_API_KEY must be configured with a secure key (at least 16 characters)."
            )
        return v


settings = Settings()
