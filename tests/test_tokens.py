"""令牌刷新轮换、登出撤销与类型隔离测试。"""

from sqlalchemy import text


async def register(client, email, password="secret123"):
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201
    return response.json()


async def login(client, email, password="secret123"):
    response = await client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    assert response.status_code == 200
    return response.json()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


async def test_refresh_rotates_token(client):
    await register(client, "refresh1@example.com")
    tokens = await login(client, "refresh1@example.com")
    old_refresh = tokens["refresh_token"]

    response = await client.post(
        "/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["access_token"]
    assert new_tokens["refresh_token"] != old_refresh

    replay = await client.post(
        "/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert replay.status_code == 401
    assert replay.json()["detail"] == "Invalid or expired refresh token"


async def test_refresh_rejects_access_token(client):
    await register(client, "refresh2@example.com")
    tokens = await login(client, "refresh2@example.com")
    response = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert response.status_code == 401


async def test_refresh_rejects_garbage_token(client):
    response = await client.post(
        "/auth/refresh", json={"refresh_token": "not-a-jwt"}
    )
    assert response.status_code == 401


async def test_refresh_rejects_inactive_user(client, db_engine):
    await register(client, "refresh3@example.com")
    tokens = await login(client, "refresh3@example.com")
    async with db_engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET is_active=0 WHERE email=:email"),
            {"email": "refresh3@example.com"},
        )
    response = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 401


async def test_access_token_cannot_be_used_as_bearer_after_logout(client):
    await register(client, "logout1@example.com")
    tokens = await login(client, "logout1@example.com")

    response = await client.post("/auth/logout", headers=auth(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out"

    me = await client.get("/users/me", headers=auth(tokens["access_token"]))
    assert me.status_code == 401

    fresh = await login(client, "logout1@example.com")
    me = await client.get("/users/me", headers=auth(fresh["access_token"]))
    assert me.status_code == 200


async def test_logout_with_refresh_revokes_both(client):
    await register(client, "logout2@example.com")
    tokens = await login(client, "logout2@example.com")

    response = await client.post(
        "/auth/logout",
        headers=auth(tokens["access_token"]),
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 200

    me = await client.get("/users/me", headers=auth(tokens["access_token"]))
    assert me.status_code == 401

    refreshed = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 401


async def test_refresh_token_cannot_call_api(client):
    await register(client, "typecheck@example.com")
    tokens = await login(client, "typecheck@example.com")
    me = await client.get("/users/me", headers=auth(tokens["refresh_token"]))
    assert me.status_code == 401
