"""应用配置：从环境变量 / .env 加载，并在生产环境下强制校验关键项。"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_SECRET_KEY = "your-secret-key-here-change-in-production"
INSECURE_SECRET_KEYS = {
    INSECURE_SECRET_KEY,
    "change-me-to-a-random-48-char-string",
}
MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    """应用配置，通过环境变量或 .env 文件加载。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: str = "development"
    DATABASE_URL: str = "mysql+asyncmy://root:password@localhost:3306/fastapi_user"
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REDIS_URL: str = "redis://localhost:6379/0"

    @model_validator(mode="after")
    def _validate_secret_key(self) -> "Settings":
        """生产环境下拒绝占位或过短的 SECRET_KEY，避免用公开密钥签发 JWT。

        开发环境不拦，否则本地跑测试还要先造一个密钥；
        但只要 ENV=production，配置有问题就在启动时直接失败，而不是悄悄带病运行。
        """
        if self.ENV.strip().lower() != "production":
            return self
        if self.SECRET_KEY in INSECURE_SECRET_KEYS:
            raise ValueError(
                "ENV=production 时必须显式设置 SECRET_KEY，当前仍是文档里的占位值"
            )
        if len(self.SECRET_KEY) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                f"ENV=production 时 SECRET_KEY 至少需要 {MIN_SECRET_KEY_LENGTH} 个字符"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """返回缓存的 Settings 实例。"""
    return Settings()


settings = get_settings()
