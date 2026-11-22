"""CaspianX configuration: simulation-scoped and safe by default.

Only reads configuration. Does not contact external services.
Never print or serialize team credentials in diagnostics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.constants import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    EVAL_SESSION_TOUCH_LIMIT,
    LIVE_CONVERSATION_MAX_TURNS,
    MAX_CONCURRENT_REQUESTS,
    PRACTICE_SESSION_TOUCH_LIMIT,
    REQUESTS_PER_MINUTE,
    TARGET_API_BASE_URL,
    TARGET_API_HOST,
)


class Settings(BaseSettings):
    """Environment-backed settings with locked-down API scope.

    No outbound requests are enabled by default, even when a key is present.
    An explicit runtime transport will still need to enforce the policy.
    """

    model_config = SettingsConfigDict(
        env_prefix="CASPIANX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        validate_default=True,
    )

    app_name: str = "CaspianX"
    environment: Literal["development", "test", "production"] = "development"
    scenario: Literal["practice", "eval"] = "practice"
    dry_run: bool = True

    target_api_base_url: str = TARGET_API_BASE_URL
    team_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    openai_model: str = ""

    http_timeout_seconds: float = Field(default=DEFAULT_HTTP_TIMEOUT_SECONDS, ge=120, le=300)
    requests_per_minute: int = Field(default=REQUESTS_PER_MINUTE, ge=1, le=REQUESTS_PER_MINUTE)
    max_concurrent_requests: int = Field(
        default=MAX_CONCURRENT_REQUESTS, ge=1, le=MAX_CONCURRENT_REQUESTS
    )
    practice_touch_limit: int = Field(
        default=PRACTICE_SESSION_TOUCH_LIMIT, ge=1, le=PRACTICE_SESSION_TOUCH_LIMIT
    )
    eval_touch_limit: int = Field(
        default=EVAL_SESSION_TOUCH_LIMIT, ge=1, le=EVAL_SESSION_TOUCH_LIMIT
    )
    live_conversation_turn_limit: int = Field(
        default=LIVE_CONVERSATION_MAX_TURNS, ge=1, le=LIVE_CONVERSATION_MAX_TURNS
    )

    story_timezone: str = "Europe/Berlin"
    sqlite_path: Path = Path("data/caspianx.sqlite3")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @field_validator("target_api_base_url")
    @classmethod
    def enforce_simulation_scope(cls, value: str) -> str:
        """Restrict the API base URL to the official simulation endpoint."""
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname != TARGET_API_HOST
            or parsed.port is not None
            or parsed.path.rstrip("/") != "/v1"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Only the official revel8 simulation API /v1 is permitted")
        return TARGET_API_BASE_URL

    @field_validator("story_timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        """Verify that the timezone is a recognized IANA timezone."""
        try:
            ZoneInfo(value)
        except (KeyError, ValueError) as exc:
            raise ValueError("Invalid IANA time zone") from exc
        return value

    @model_validator(mode="after")
    def protect_eval_environment(self) -> "Settings":
        # Evaluation must never be selected accidentally while dry-run testing.
        """Disallow evaluation mode outside the production environment."""
        if self.scenario == "eval" and self.environment != "production":
            raise ValueError("eval scenario requires environment=production")
        return self

    @property
    def allowed_touch_limit(self) -> int:
        """Return the configured contact limit for the selected scenario."""
        return self.eval_touch_limit if self.scenario == "eval" else self.practice_touch_limit

    def public_diagnostics(self) -> dict[str, str | int | bool]:
        """Safe operational summary; intentionally omits all secrets and paths."""
        return {
            "app_name": self.app_name,
            "environment": self.environment,
            "scenario": self.scenario,
            "dry_run": self.dry_run,
            "target_api_base_url": self.target_api_base_url,
            "http_timeout_seconds": self.http_timeout_seconds,
            "requests_per_minute": self.requests_per_minute,
            "max_concurrent_requests": self.max_concurrent_requests,
            "allowed_touch_limit": self.allowed_touch_limit,
            "story_timezone": self.story_timezone,
        }
