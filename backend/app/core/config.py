from functools import lru_cache
from pathlib import Path

from pydantic import EmailStr, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.local_secrets import load_or_create_local_secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    app_name: str = "AI Research Assistant"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://research:research@postgres:5432/research"
    # Development defaults; configure credentials and HTTPS before production use.
    jwt_secret: str = Field(default="", repr=False)
    encryption_key: str = Field(default="", repr=False)
    local_secrets_file: Path = Path("data/local-secrets.json")
    admin_email: EmailStr = "admin@example.com"
    admin_password: str = Field(default="administrator-password", repr=False)
    cookie_secure: bool = False
    access_token_expire_minutes: int = 720
    allowed_origins: str = "http://localhost:5173,http://localhost:8080"
    upload_dir: Path = Path("/data/uploads")
    max_upload_mb: int = 25
    allow_private_api_endpoints: bool = False

    @model_validator(mode="after")
    def resolve_local_secrets(self) -> "Settings":
        if not self.jwt_secret or not self.encryption_key:
            local = load_or_create_local_secrets(self.local_secrets_file)
            self.jwt_secret = self.jwt_secret or local["jwt_secret"]
            self.encryption_key = self.encryption_key or local["encryption_key"]
        return self

    @property
    def allowed_origin_list(self) -> list[str]:
        """把 Docker 环境变量中的逗号分隔来源转为 CORS 白名单。"""
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
