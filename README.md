# FastAPI User Auth System

基于 **FastAPI** 与 **MySQL** 的用户认证与授权系统，支持双 Token（JWT）认证、刷新轮换与 Redis 黑名单撤销，以及用户-角色-权限的通用 RBAC。

## 项目目标

- 用户注册与登录（OAuth2 密码表单）
- 双 Token：短时 Access Token + 长时 Refresh Token
- 刷新轮换：每次刷新签发新令牌对并撤销旧 Refresh Token，防重放
- 登出撤销：将 Token 的 `jti` 写入 Redis 黑名单（TTL = 令牌剩余寿命）
- 通用 RBAC：用户-角色-权限关联与细粒度权限点校验
- 异步数据库访问（SQLAlchemy 2.0 + asyncmy）与 Alembic 迁移

## 技术栈

- **FastAPI** — Web 框架
- **SQLAlchemy 2.0（异步）+ asyncmy** — ORM 与 MySQL 异步驱动
- **Alembic** — 数据库迁移
- **Pydantic / pydantic-settings** — 数据校验与配置管理
- **python-jose** — JWT 签发与校验
- **passlib[bcrypt] + bcrypt** — 密码哈希
- **Redis（redis-py asyncio）** — Token 黑名单存储
- **pytest + httpx + pytest-asyncio** — 接口测试
- **uvicorn** — ASGI 服务器

## 数据库

本项目使用 **MySQL** 作为数据库，通过 `asyncmy` 异步驱动连接，连接串由环境变量 `DATABASE_URL` 配置；Token 黑名单存储在 **Redis**，地址由 `REDIS_URL` 配置。

## 环境变量

复制 `.env.example` 为 `.env` 并按需修改：

```bash
DATABASE_URL=mysql+asyncmy://root:password@localhost:3306/fastapi_user
SECRET_KEY=your-secret-key-here-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
REDIS_URL=redis://localhost:6379/0
```

## 快速开始

```bash
# 1. 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate

# 2. 安装依赖（含开发/测试依赖）
pip install -r requirements-dev.txt

# 3. 配置环境变量
cp .env.example .env

# 4. 启动 Redis（黑名单需要；无 Redis 时测试会用 fakeredis 替代）
redis-server

# 5. 启动开发服务器（首次启动会自动创建数据库表并写入默认角色）
uvicorn app.main:app --reload
```

> 说明：开发环境下，应用在启动时会通过 `Base.metadata.create_all` 自动创建数据表并幂等写入默认 RBAC 种子；生产环境请使用 Alembic 迁移。

## Docker 部署（可选）

项目自带 `Dockerfile` 与 `docker-compose.yml`，一条命令即可启动 **FastAPI 应用 + MySQL 8.4 + Redis 7**：

```bash
# 启动（首次会自动构建镜像）
docker compose up -d --build

# 查看启动日志
docker compose logs -f app

# API 文档
open http://localhost:8000/docs

# 停止服务（保留 MySQL 数据卷）
docker compose down

# 停止并删除 MySQL 数据卷（彻底重置）
docker compose down -v
```

说明：

- `app` 容器启动时自动执行 `alembic upgrade head` 后再启动 `uvicorn`，无需手动迁移
- `db`（MySQL）与 `redis` 服务均带健康检查，`app` 会等它们就绪后再启动
- MySQL 数据持久化在 `mysql_data` 卷中；`db` 端口默认**不映射到宿主机**，避免与本机 MySQL 冲突，如需宿主机直连可自行添加 `ports: - "3306:3306"`
- `app` 容器内的 `REDIS_URL=redis://redis:6379/0` 指向 compose 的 `redis` 服务，无需额外配置
- 可用环境变量覆盖默认值（不设置时默认：`MYSQL_ROOT_PASSWORD=changeme`、`MYSQL_DATABASE=fastapi_user`），例如：
  ```bash
  MYSQL_ROOT_PASSWORD=your-db-pass SECRET_KEY=your-secret docker compose up -d --build
  ```
- 生产环境务必通过环境变量覆盖 `SECRET_KEY` 等敏感配置，不要使用默认值

## 双 Token 与撤销（Redis 黑名单）

JWT 的 Payload 统一包含 `sub`（用户 id）、`type`（`access` / `refresh`）、`jti`（唯一 id）与 `exp`：

- **Access Token**：默认 30 分钟有效，用于调用受保护接口（`Authorization: Bearer <token>`）
- **Refresh Token**：默认 7 天有效，只能用于 `/auth/refresh` 换取新的令牌对，不能访问业务接口

撤销机制：

- `POST /auth/refresh`：校验 Refresh Token 后，先将其 `jti` 写入 Redis 黑名单（TTL = 剩余寿命），再签发新的令牌对。旧 Refresh Token 一旦被重放，立即返回 401
- `POST /auth/logout`：将当前 Access Token 的 `jti` 写入黑名单；请求体可携带 `refresh_token` 一并撤销
- `get_current_user` 在每次鉴权时先解码校验签名，再检查 `jti` 是否在黑名单中
- Redis 键格式：`token:blacklist:<jti>`，天然自动过期，无需手动清理

测试环境无需真实 Redis：`tests/conftest.py` 用 `fakeredis` 覆盖 `get_redis` 依赖。

## 数据库迁移（Alembic）

生产环境建议使用 Alembic 管理数据库结构，迁移脚本位于 `alembic/versions/`。

```bash
# 应用迁移到数据库
alembic upgrade head

# 模型变更后生成新的迁移脚本（需要可连接的数据库）
alembic revision --autogenerate -m "describe the change"

# 回滚最近一次迁移
alembic downgrade -1

# 查看迁移历史与当前版本
alembic history
alembic current
```

连接串统一从 `.env` 中的 `DATABASE_URL` 读取，由 `app/config.py` 注入到 Alembic。

## 分层架构

项目按 **routers（路由）/ schemas（数据校验）/ models（数据库模型）/ services（业务逻辑）** 四层组织，依赖方向自上而下单向：

```text
HTTP 请求
   │
   ▼
┌─────────────────────────────────────────────┐
│ routers/   HTTP 层：参数解析、鉴权依赖、状态码   │
│   deps.py     get_current_user / require_   │
│   auth.py     permission 等共享依赖           │
│   users.py                                  │
└───────────────┬─────────────────────────────┘
                │ 调用 services，捕获业务异常并转 HTTPException
                ▼
┌─────────────────────────────────────────────┐
│ schemas/  Pydantic 层：请求/响应 DTO 与校验    │
│   auth.py  user.py  role.py                 │
└───────────────┬─────────────────────────────┘
                │（DTO 由路由层构造/校验）
                ▼
┌─────────────────────────────────────────────┐
│ services/  业务层：用例编排、规则、事务边界      │
│   auth_service.py   注册/登录/刷新/登出        │
│   user_service.py   用户 CRUD/角色分配/软删除  │
│   token_service.py  JWT 签发/解码/撤销        │
│   rbac_service.py   权限判定/种子数据          │
│   errors.py         业务异常（路由层转 HTTP）  │
└───────────────┬─────────────────────────────┘
                │ 通过 SQLAlchemy 异步会话访问数据
                ▼
┌─────────────────────────────────────────────┐
│ models/   ORM 层：表结构与关系                │
│   user.py  role.py  permission.py           │
│   associations.py   user_roles/role_perms   │
└───────────────┬─────────────────────────────┘
                ▼
   database.py（engine/会话） + core/（security/redis 基础设施）
```

分层规则：

- **routers** 只做 HTTP 翻译：解析 `schemas` DTO、声明 `Depends` 鉴权、调用 `services`，把业务异常映射为 `HTTPException`，不写 SQL
- **schemas** 只做数据校验与序列化，不含业务逻辑
- **services** 承载业务规则（邮箱唯一、默认角色、刷新轮换、软删除等），不感知 `Request/Response/HTTPException`
- **models** 只定义表结构与关系，不包含查询逻辑之外的业务
- 依赖只允许“上层 → 下层”，禁止反向引用；`services` 之间可互相调用（如 `auth_service` → `user_service`）

## 权限管理（RBAC）

采用用户-角色-权限五表关联模型：

- `users`、`roles`、`permissions` 三张实体表
- `user_roles`、`role_permissions` 两张关联表（外键级联删除）

默认角色与权限（由迁移脚本与 `app/core/rbac.py` 幂等种子写入）：

| 角色 | 权限 |
| --- | --- |
| `admin` | `user:list`、`user:delete`、`role:assign` |
| `user` | 无 |

鉴权方式：路由通过 `Depends(require_permission("user:list"))` 等声明所需权限；
`require_permission` 在 `app/routers/deps.py` 中声明，由 `app/services/rbac_service.py` 按“用户 → 角色 → 权限”实时查库校验，未授权返回 403。

相关 API：

- `POST /users/assign-role`：为用户分配角色（需 `role:assign`）
- `DELETE /users/{user_id}/roles/{role_name}`：移除用户角色（需 `role:assign`）

用户注册时自动获得 `user` 角色；JWT 中仅含用户 id，角色与权限每次请求实时读取，改角色或软删除即刻生效。

## 主要 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/auth/register` | 注册（默认分配 `user` 角色） |
| `POST` | `/auth/login` | OAuth2 密码表单登录，返回双 Token |
| `POST` | `/auth/refresh` | 用 Refresh Token 刷新并轮换令牌对 |
| `POST` | `/auth/logout` | 登出，撤销当前 Token（可带 refresh_token） |
| `GET` | `/users/me` | 当前用户信息 |
| `PUT` | `/users/me` | 更新当前用户 `full_name` |
| `GET` | `/users` | 用户列表（需 `user:list`） |
| `POST` | `/users/assign-role` | 分配角色（需 `role:assign`） |
| `DELETE` | `/users/{user_id}` | 软删除用户（需 `user:delete`） |

## 运行测试

测试基于 `pytest-asyncio` 与 `httpx.AsyncClient`，使用内存 SQLite（`aiosqlite`）作为独立测试库，
并以 `fakeredis` 替代真实 Redis，无需启动 MySQL 或 Redis。每个测试用例会创建独立的内存数据库，结束后自动清理，互不影响。

```bash
# 安装测试依赖（已在 requirements-dev.txt 中）
pip install -r requirements-dev.txt

# 运行全部测试
pytest -v
```

说明：`tests/conftest.py` 通过 `app.dependency_overrides` 将应用的 `get_db` / `get_redis` 依赖分别覆盖为测试库连接与 `fakeredis`。
