"""用户管理端点测试（含管理员权限场景）。"""

import uuid

from sqlalchemy import text


async def register(client, email, password="secret123", full_name=None):
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert response.status_code == 201
    return response.json()


async def login(client, email, password="secret123"):
    response = await client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


async def create_admin(client, db_engine, email="admin@example.com"):
    await register(client, email, full_name="Admin")
    async with db_engine.begin() as conn:
        role_id = (
            await conn.execute(text("SELECT id FROM roles WHERE name='admin'"))
        ).scalar_one()
        user_id = (
            await conn.execute(
                text("SELECT id FROM users WHERE email=:email"), {"email": email}
            )
        ).scalar_one()
        await conn.execute(
            text("INSERT INTO user_roles (user_id, role_id) VALUES (:u, :r)"),
            {"u": user_id, "r": role_id},
        )
    return await login(client, email)


async def test_get_me(client):
    user = await register(client, "me@example.com", full_name="Me")
    token = await login(client, "me@example.com")
    response = await client.get("/users/me", headers=auth(token))
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user["id"]
    assert data["email"] == "me@example.com"
    assert data["full_name"] == "Me"
    assert [r["name"] for r in data["roles"]] == ["user"]
    assert data["is_active"] is True


async def test_get_me_requires_auth(client):
    response = await client.get("/users/me")
    assert response.status_code == 401


async def test_update_full_name(client):
    await register(client, "upd@example.com", full_name="Old")
    token = await login(client, "upd@example.com")
    response = await client.put(
        "/users/me", headers=auth(token), json={"full_name": "New"}
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "New"

    response = await client.put("/users/me", headers=auth(token), json={})
    assert response.status_code == 200
    assert response.json()["full_name"] == "New"


async def test_list_users_admin_only(client, db_engine):
    await register(client, "normal@example.com")
    token = await login(client, "normal@example.com")
    forbidden = await client.get("/users", headers=auth(token))
    assert forbidden.status_code == 403

    admin_token = await create_admin(client, db_engine, email="admin2@example.com")
    allowed = await client.get("/users", headers=auth(admin_token))
    assert allowed.status_code == 200
    emails = {u["email"] for u in allowed.json()}
    assert "admin2@example.com" in emails
    assert "normal@example.com" in emails


async def test_assign_role_by_admin(client, db_engine):
    admin_token = await create_admin(client, db_engine)
    target = await register(client, "target@example.com")
    response = await client.post(
        "/users/assign-role",
        headers=auth(admin_token),
        json={"user_id": target["id"], "role_name": "admin"},
    )
    assert response.status_code == 200
    role_names = [r["name"] for r in response.json()["roles"]]
    assert set(role_names) == {"user", "admin"}


async def test_assign_role_invalid_role(client, db_engine):
    admin_token = await create_admin(client, db_engine)
    target = await register(client, "target2@example.com")
    response = await client.post(
        "/users/assign-role",
        headers=auth(admin_token),
        json={"user_id": target["id"], "role_name": "superuser"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Role not found"


async def test_assign_role_user_not_found(client, db_engine):
    admin_token = await create_admin(client, db_engine)
    response = await client.post(
        "/users/assign-role",
        headers=auth(admin_token),
        json={"user_id": str(uuid.uuid4()), "role_name": "user"},
    )
    assert response.status_code == 404


async def test_assign_role_requires_admin(client, db_engine):
    await register(client, "normal2@example.com")
    token = await login(client, "normal2@example.com")
    response = await client.post(
        "/users/assign-role",
        headers=auth(token),
        json={"user_id": str(uuid.uuid4()), "role_name": "user"},
    )
    assert response.status_code == 403


async def test_assign_role_idempotent(client, db_engine):
    admin_token = await create_admin(client, db_engine)
    target = await register(client, "target3@example.com")
    for _ in range(2):
        response = await client.post(
            "/users/assign-role",
            headers=auth(admin_token),
            json={"user_id": target["id"], "role_name": "admin"},
        )
        assert response.status_code == 200
    role_names = [r["name"] for r in response.json()["roles"]]
    assert set(role_names) == {"user", "admin"}


async def test_remove_role_revokes_access(client, db_engine):
    admin_token = await create_admin(client, db_engine)
    worker = await register(client, "worker@example.com", full_name="Worker")
    worker_token = await login(client, "worker@example.com")

    assigned = await client.post(
        "/users/assign-role",
        headers=auth(admin_token),
        json={"user_id": worker["id"], "role_name": "admin"},
    )
    assert assigned.status_code == 200

    allowed = await client.get("/users", headers=auth(worker_token))
    assert allowed.status_code == 200

    removed = await client.delete(
        f"/users/{assigned.json()['id']}/roles/admin", headers=auth(admin_token)
    )
    assert removed.status_code == 200
    assert [r["name"] for r in removed.json()["roles"]] == ["user"]

    forbidden = await client.get("/users", headers=auth(worker_token))
    assert forbidden.status_code == 403


async def test_soft_delete_by_admin(client, db_engine):
    admin_token = await create_admin(client, db_engine)
    target = await register(client, "victim@example.com")
    victim_token = await login(client, "victim@example.com")

    response = await client.delete(
        f"/users/{target['id']}", headers=auth(admin_token)
    )
    assert response.status_code == 200
    assert response.json()["message"] == "User deactivated"

    response = await client.get("/users/me", headers=auth(victim_token))
    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user"


async def test_remove_role_user_not_found(client, db_engine):
    admin_token = await create_admin(client, db_engine)
    response = await client.delete(
        f"/users/{uuid.uuid4()}/roles/admin", headers=auth(admin_token)
    )
    assert response.status_code == 404


async def test_remove_role_role_not_found(client, db_engine):
    admin_token = await create_admin(client, db_engine)
    target = await register(client, "target4@example.com")
    response = await client.delete(
        f"/users/{target['id']}/roles/superuser", headers=auth(admin_token)
    )
    assert response.status_code == 400


async def test_soft_delete_missing_user(client, db_engine):
    admin_token = await create_admin(client, db_engine)
    response = await client.delete(
        f"/users/{uuid.uuid4()}", headers=auth(admin_token)
    )
    assert response.status_code == 404


async def test_delete_requires_admin(client, db_engine):
    await register(client, "normal3@example.com")
    token = await login(client, "normal3@example.com")
    response = await client.delete(
        f"/users/{uuid.uuid4()}", headers=auth(token)
    )
    assert response.status_code == 403
