"""注册、登录与鉴权依赖缓存测试。"""

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.database import get_db
from app.main import app
from app.models.permission import PERM_USER_LIST
from app.routers import deps
from app.routers.deps import get_current_active_user, oauth2_scheme, require_permission


async def register(client, email, password="secret123", full_name=None):
    return await client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )


async def login(client, email, password="secret123"):
    response = await client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}
async def test_register_success(client):
    response = await register(client, "alice@example.com", full_name="Alice")
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["full_name"] == "Alice"
    assert data["is_active"] is True
    assert data["roles"][0]["name"] == "user"
    assert "id" in data
    assert "created_at" in data
    assert "hashed_password" not in data


async def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "secret123"}
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 400
    assert second.json()["detail"] == "Email already registered"


async def test_register_invalid_email(client):
    response = await client.post(
        "/auth/register", json={"email": "not-an-email", "password": "secret123"}
    )
    assert response.status_code == 422


async def test_login_success(client):
    await register(client, "bob@example.com")
    response = await client.post(
        "/auth/login", data={"username": "bob@example.com", "password": "secret123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["refresh_token"]


async def test_login_wrong_password(client):
    await register(client, "carol@example.com")
    response = await client.post(
        "/auth/login", data={"username": "carol@example.com", "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


async def test_get_current_user_runs_once_per_request(client):
    """同一请求内两条依赖链共享 get_current_user，每请求只解析一次。"""
    await register(client, "cache@example.com")
    token = await login(client, "cache@example.com")

    original = deps.get_current_user
    counter = {"calls": 0}

    async def counting_get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db),
        redis: Redis = Depends(get_redis),
    ):
        counter["calls"] += 1
        return await original(token=token, db=db, redis=redis)

    demo = APIRouter()

    @demo.get("/_demo/cache", response_model=dict[str, str])
    async def demo_route(
        active_user=Depends(get_current_active_user),
        permitted_user=Depends(require_permission(PERM_USER_LIST)),
    ):
        return {"ok": "true"}

    app.include_router(demo)
    app.dependency_overrides[original] = counting_get_current_user
    demo_routes = list(demo.routes)
    try:
        # 普通用户无 user:list 权限 -> 403；但 get_current_user 只应执行一次
        resp = await client.get("/_demo/cache", headers=auth(token))
        assert resp.status_code == 403
        assert counter["calls"] == 1

        # 第二个请求是新作用域，重新计数
        resp = await client.get("/_demo/cache", headers=auth(token))
        assert resp.status_code == 403
        assert counter["calls"] == 2

        # 真实端点 /users/me 同样每个请求只解析一次
        resp = await client.get("/users/me", headers=auth(token))
        assert resp.status_code == 200
        assert counter["calls"] == 3
    finally:
        app.dependency_overrides.pop(original, None)
        for route in list(app.routes):
            if any(route is r for r in demo_routes):
                app.routes.remove(route)
