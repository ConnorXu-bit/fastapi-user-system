"""配置校验测试：生产环境必须使用真实的 SECRET_KEY。"""

import pytest
from pydantic import ValidationError

from app.config import INSECURE_SECRET_KEY, MIN_SECRET_KEY_LENGTH, Settings


def test_development_allows_default_secret_key():
    """开发环境不拦，本地开箱即用。"""
    settings = Settings(ENV="development")
    assert settings.SECRET_KEY == INSECURE_SECRET_KEY


def test_production_rejects_placeholder_secret_key():
    """生产环境仍用文档里的占位密钥 → 直接启动失败。"""
    with pytest.raises(ValidationError):
        Settings(ENV="production", SECRET_KEY=INSECURE_SECRET_KEY)


def test_production_rejects_short_secret_key():
    """生产环境密钥过短 → 直接启动失败。"""
    with pytest.raises(ValidationError):
        Settings(ENV="production", SECRET_KEY="short-key")


def test_production_accepts_strong_secret_key():
    """生产环境配置了足够强的密钥 → 正常加载。"""
    settings = Settings(ENV="production", SECRET_KEY="k" * MIN_SECRET_KEY_LENGTH)
    assert settings.ENV == "production"
