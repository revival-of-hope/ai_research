from functools import lru_cache
from pathlib import Path

from pydantic import EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Research Assistant"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://research:research@postgres:5432/research"
    jwt_secret: str
    encryption_key: str
    admin_email: EmailStr
    admin_password: str
    cookie_secure: bool = False
    access_token_expire_minutes: int = 720
    allowed_origins: str = "http://localhost:5173,http://localhost:8080"
    upload_dir: Path = Path("/data/uploads")
    max_upload_mb: int = 25
    allow_private_api_endpoints: bool = False

    @property
    def allowed_origin_list(self) -> list[str]:
        """把 Docker 环境变量中的逗号分隔来源转为 CORS 白名单。"""
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
