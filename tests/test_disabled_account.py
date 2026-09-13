"""停用（软删除）账号的边界行为测试。"""

from sqlalchemy import text

from test_users import auth, create_admin, login, register


async def deactivate(db_engine, email):
    async with db_engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET is_active=0 WHERE email=:email"), {"email": email}
        )


async def test_login_rejects_inactive_user(client, db_engine):
    """已停用的账号不应能重新登录换取新令牌。"""
    await register(client, "disabled@example.com")
    await deactivate(db_engine, "disabled@example.com")

    response = await client.post(
        "/auth/login",
        data={"username": "disabled@example.com", "password": "secret123"},
    )

    assert response.status_code == 403


async def test_inactive_user_cannot_use_existing_token(client, db_engine):
    """停用前签发的令牌，也不应再访问受权限保护的接口。"""
    token = await create_admin(client, db_engine, email="admin9@example.com")
    await deactivate(db_engine, "admin9@example.com")

    response = await client.get("/users", headers=auth(token))

    assert response.status_code in (401, 403)
