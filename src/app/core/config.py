from functools import lru_cache
from urllib.parse import urlparse

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "FastAPI SaaS Starter"
    app_env: str = "development"  # development, testing, production
    debug: bool = False
    enable_openapi: bool = True  # Set to False in production

    # Security
    log_user_emails: bool = False  # Set to False in production for GDPR compliance
    trusted_proxy_ips: list[str] = []  # List of trusted proxy IPs for X-Forwarded-For
    allowed_app_url_domains: list[str] = ["localhost", "127.0.0.1"]  # Allowed domains for APP_URL
    # CSP for production (no unsafe-inline, no external CDN) - set to empty string to use default
    csp_production: str = "default-src 'self'; frame-ancestors 'none'"

    # Database
    database_url: str
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_ssl_mode: str = "prefer"  # disable, prefer, require, verify-ca, verify-full

    # Shutdown
    shutdown_grace_period: int = 30

    # Auth
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 1

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if v == "change-this-to-a-secure-random-string":
            raise ValueError(
                "JWT_SECRET_KEY must be changed from default value. "
                "Generate a secure secret with: openssl rand -hex 32"
            )
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, v: list[str]) -> list[str]:
        """Validate CORS origins - reject wildcards when credentials are used."""
        for origin in v:
            if origin == "*":
                raise ValueError(
                    "CORS wildcard '*' is not allowed when allow_credentials=True. "
                    "Specify explicit origins instead."
                )
        return v

    @field_validator("app_url")
    @classmethod
    def validate_app_url(cls, v: str, info: ValidationInfo) -> str:
        """Validate APP_URL is from allowed domain list to prevent SSRF in emails."""
        # Get allowed domains from values or use default
        allowed = info.data.get("allowed_app_url_domains", ["localhost", "127.0.0.1"])
        parsed = urlparse(v)
        hostname = parsed.hostname or ""

        # Check if hostname matches any allowed domain
        if not any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed):
            raise ValueError(
                f"APP_URL domain '{hostname}' not in allowed list. "
                f"Add it to ALLOWED_APP_URL_DOMAINS or use: {allowed}"
            )
        return v

    # Temporal
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "main-queue"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Metrics
    metrics_api_key: str | None = None  # If set, /metrics requires this key

    # Email (Resend)
    resend_api_key: str | None = None  # If not set, emails are logged but not sent
    email_from: str = "noreply@example.com"
    email_verification_expire_hours: int = 24
    email_send_timeout_seconds: int = 10  # Timeout for email API calls
    app_url: str = "http://localhost:3000"  # Frontend URL for verification links

    # Invites
    invite_expire_days: int = 7

    # Cleanup (Temporal scheduled workflow)
    cleanup_schedule: str | None = None  # Cron syntax, e.g., "0 3 * * *" for daily at 3am UTC
    cleanup_retention_days: int = 30  # Delete tokens expired more than this many days ago

    # Redis (optional - app works without it)
    redis_url: str | None = None  # e.g., "redis://localhost:6379/0"
    redis_pool_size: int = 10

    # Rate Limiting (global middleware - DoS protection)
    global_rate_limit_per_second: int = 10  # Max requests/second per IP
    global_rate_limit_burst: int = 20  # Token bucket burst capacity


@lru_cache
def get_settings() -> Settings:
    return Settings()
