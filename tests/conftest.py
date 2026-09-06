"""pytest 共享 fixtures：内存 SQLite 测试库 + get_db 依赖覆盖。"""

from collections.abc import AsyncGenerator

import httpx
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.services.rbac_service import seed_rbac
from app.core.redis import get_redis
from app.database import Base, get_db
from app.main import app


@pytest_asyncio.fixture
async def db_engine() -> AsyncGenerator:
    """每个测试独立的内存 SQLite 引擎，测试结束自动释放。"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await seed_rbac(session)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """直接访问测试库的会话，便于测试内修改数据（如提升 admin）。"""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine) -> AsyncGenerator[httpx.AsyncClient, None]:
    """基于 httpx.AsyncClient + ASGITransport 的测试客户端。"""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    fake_redis: Redis = FakeAsyncRedis(decode_responses=True)

    async def override_get_redis() -> AsyncGenerator[Redis, None]:
        yield fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_redis, None)
    await fake_redis.aclose()
