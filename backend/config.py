from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    openai_api_key: str = ""
    admin_password: str = "admin123"
    jwt_secret: str = "change-this-secret-in-production-32chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    allowed_origins: str = "https://legalassistglobal.com,http://localhost:3000"

    # ── Neon / PostgreSQL individual connection params (preferred) ──
    db_host: str = ""
    db_user: str = "neondb_owner"
    db_password: str = ""
    db_port: str = "5432"
    db_name: str = "neondb"

    # ── Fallback full URL (used if DB_HOST not set) ──
    database_url: str = "sqlite:///./legalassist.db"

    site_url: str = "https://legalassistglobal.com"
    site_sitemap_url: str = "https://legalassistglobal.com/page-sitemap.xml"

    app_env: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
