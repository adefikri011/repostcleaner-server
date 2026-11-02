from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    session_secret: SecretStr
    session_expire_hours: int = 168
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    frontend_origin: str = "http://localhost:5173"
    environment: Literal["development", "test", "production"] = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("session_expire_hours")
    @classmethod
    def validate_session_expiry(cls, value: int) -> int:
        if not 1 <= value <= 24 * 90:
            raise ValueError("SESSION_EXPIRE_HOURS must be between 1 and 2160")
        return value

    @field_validator("frontend_origin")
    @classmethod
    def validate_frontend_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("FRONTEND_ORIGIN must contain at least one origin")
        for origin in origins:
            parsed = urlparse(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
                or origin == "*"
            ):
                raise ValueError("FRONTEND_ORIGIN must contain exact HTTP(S) origins")
        return ",".join(origins)

    @field_validator("session_secret")
    @classmethod
    def validate_session_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("SESSION_SECRET must contain at least 32 bytes")
        return value

    @model_validator(mode="after")
    def validate_cookie_settings(self) -> "Settings":
        if self.environment == "production" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be enabled in production")
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE is required when COOKIE_SAMESITE is none")
        return self

    @property
    def frontend_origins(self) -> list[str]:
        return self.frontend_origin.split(",")


@lru_cache
def get_settings() -> Settings:
    return Settings()
