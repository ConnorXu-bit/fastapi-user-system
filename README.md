# FastAPI User Auth System

基于 **FastAPI + MySQL + Redis** 的异步用户认证与授权系统：OAuth2 密码表单登录、双 Token（JWT）认证、刷新轮换防重放、Redis 黑名单即时撤销，以及用户-角色-权限的通用 RBAC。

## 目录

- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [环境变量](#环境变量)
- [Docker 部署（可选）](#docker-部署可选)
- [认证机制（双 Token 与撤销）](#认证机制双-token-与撤销)
- [权限管理（RBAC）](#权限管理rbac)
- [API 一览与调用示例](#api-一览与调用示例)
- [数据库迁移（Alembic）](#数据库迁移alembic)
- [项目结构与架构](#项目结构与架构)
- [运行测试](#运行测试)

## 功能特性

- 用户注册与登录（OAuth2 Password Flow，`username` 即邮箱）
- 双 Token 认证：**Access Token**（默认 30 分钟）访问业务接口，**Refresh Token**（默认 7 天）仅用于换发新令牌
- 刷新轮换防重放：每次 `POST /auth/refresh` 撤销旧 Refresh Token 并签发新令牌对，重放旧 Token 立即返回 401
- 登出即时撤销：Token 的 `jti` 写入 Redis 黑名单（TTL = 令牌剩余寿命），无需手动清理
- 通用 RBAC：用户-角色-权限五表关联，权限点细粒度校验，角色/权限变更实时生效
- 全异步 I/O：SQLAlchemy 2.0 + asyncmy，Alembic 管理迁移
- 开箱即用：开发环境启动自动建表并幂等写入默认角色；Docker Compose 一键拉起应用 + MySQL 8.4 + Redis 7
- 测试零依赖：pytest + 内存 SQLite（aiosqlite）+ fakeredis，无需启动 MySQL / Redis

## 技术栈

| 分类 | 选型 |
| --- | --- |
| Web 框架 | FastAPI + uvicorn |
| 数据库 / 驱动 | MySQL 8.x + asyncmy（异步） |
| ORM / 迁移 | SQLAlchemy 2.0（async）+ Alembic |
| 校验 / 配置 | Pydantic 2 + pydantic-settings |
| 认证 / 密码 | python-jose（JWT）、passlib[bcrypt] |
| 黑名单存储 | Redis（redis-py asyncio） |
| 测试 | pytest + pytest-asyncio + httpx、aiosqlite + fakeredis |

## 快速开始

环境要求：Python 3.10+，本机可用的 MySQL 与 Redis（仅跑测试则都不需要）。

```bash
# 1. 准备数据库（MySQL 需先启动；utf8mb4 保证中文等字符完整存储）
mysql -uroot -p -e "CREATE DATABASE IF NOT EXISTS fastapi_user CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 2. 创建并激活虚拟环境，安装依赖（含测试依赖）
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 3. 从模板生成配置，并按需修改数据库口令、SECRET_KEY 等
cp .env.example .env

# 4. 启动 Redis（Token 黑名单依赖；只跑测试可跳过）
redis-server --daemonize yes

# 5. 启动开发服务器（首次启动自动建表并写入默认 RBAC 角色）
uvicorn app.main:app --reload
```

启动后访问：

- 根路径：http://localhost:8000/ （健康检查）
- 交互式 API 文档：http://localhost:8000/docs （Swagger UI）或 http://localhost:8000/redoc

> 说明：开发环境在启动时通过 `Base.metadata.create_all` 自动建表，并调用 `seed_rbac`（`app/services/rbac_service.py`）幂等写入默认角色与权限；生产环境请改用 Alembic 迁移（见下文）。

## 环境变量

配置通过 pydantic-settings 从 `.env` 或环境变量读取（`.env.example` 含全部变量与默认值）。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ENV` | `development` | 运行环境；设为 `production` 时强制校验 `SECRET_KEY` |
| `DATABASE_URL` | `mysql+asyncmy://root:password@localhost:3306/fastapi_user` | MySQL 异步连接串 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 地址（Token 黑名单） |
| `SECRET_KEY` | `your-secret-key-here-change-in-production` | JWT 签名密钥；`ENV=production` 时必须是**非占位值且长度 ≥ 32** |
| `ALGORITHM` | `HS256` | JWT 签名算法 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access Token 有效期（分钟） |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh Token 有效期（天） |
| `MYSQL_ROOT_PASSWORD` | `changeme` | 仅 Docker 部署使用：MySQL root 密码 |
| `MYSQL_DATABASE` | `fastapi_user` | 仅 Docker 部署使用：自动创建的数据库名 |

**密钥校验（fail fast）**：当 `ENV=production` 且 `SECRET_KEY` 仍是文档里的占位值、或长度不足
32 位时，应用会在**启动阶段**直接抛出校验错误，而不是用一个人人皆知的密钥悄悄对外服务。
生成方式：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

开发环境不拦截，保持开箱即用。

## Docker 部署（可选）

仓库内置 `Dockerfile` 与 `docker-compose.yml`，一条命令即可启动 **应用 + MySQL 8.4 + Redis 7**：

```bash
# 构建并启动（首次会自动构建镜像）
docker compose up -d --build

# 查看应用日志
docker compose logs -f app

# 交互式 API 文档
open http://localhost:8000/docs

# 停止服务（保留 MySQL 数据卷）
docker compose down

# 停止并删除 MySQL 数据卷（彻底重置）
docker compose down -v
```

默认行为与说明：

- `app` 启动前自动执行 `alembic upgrade head` 再启动 `uvicorn`，无需手动迁移
- MySQL 与 Redis 均配置健康检查，`app` 会等它们就绪后才启动
- MySQL 数据持久化在 `mysql_data` 卷；`db` 端口默认**不映射到宿主机**（避免与本机 MySQL 冲突），如需宿主机直连可自行添加 `ports: - "3306:3306"`
- 容器内 `REDIS_URL=redis://redis:6379/0` 自动指向 compose 的 Redis 服务，无需额外配置
- 支持用环境变量覆盖默认值，例如：
  ```bash
  MYSQL_ROOT_PASSWORD=your-db-pass SECRET_KEY=your-secret docker compose up -d --build
  ```
- 生产环境务必通过环境变量覆盖 `SECRET_KEY`、`MYSQL_ROOT_PASSWORD` 等敏感配置，不要使用默认值

## 认证机制（双 Token 与撤销）

JWT Payload 统一包含 `sub`（用户 id）、`type`（`access` / `refresh`）、`jti`（唯一标识）与 `exp`（过期时间）。

- **Access Token**：调用受保护接口，通过请求头携带 `Authorization: Bearer <access_token>`
- **Refresh Token**：只能用于 `POST /auth/refresh` 换发新令牌对，不能访问业务接口

令牌生命周期：

1. **登录** `POST /auth/login`：校验邮箱密码后签发令牌对，返回 `{access_token, refresh_token, token_type: "bearer"}`
2. **访问**：`get_current_user` 解码校验签名，确认 `type=access` 且 `jti` 不在黑名单，再实时加载用户与权限
3. **刷新** `POST /auth/refresh`：校验 Refresh Token 后，先将其 `jti` 写入黑名单（TTL = 剩余寿命），再签发新令牌对；旧 Token 被重放立即返回 401
4. **登出** `POST /auth/logout`：将当前 Access Token 的 `jti` 写入黑名单；请求体可携带 `refresh_token` 一并撤销

实现要点：

- Redis 黑名单键格式：`token:blacklist:<jti>`，随 TTL 自动过期，无需手动清理
- 每次鉴权都会先检查黑名单，登出 / 刷新后的原 Token 立即失效
- 测试环境由 `tests/conftest.py` 用 `fakeredis` 覆盖 `get_redis` 依赖，无需真实 Redis

## 权限管理（RBAC）

采用用户-角色-权限五表模型：`users`、`roles`、`permissions` 三张实体表，`user_roles`、`role_permissions` 两张关联表（外键级联删除）。

默认角色与权限（由 Alembic 迁移脚本与启动时的 `seed_rbac` 幂等写入）：

| 角色 | 权限 |
| --- | --- |
| `admin` | `user:list`、`user:delete`、`role:assign` |
| `user` | （无） |

鉴权方式：

- 用户注册时自动获得 `user` 角色
- 路由通过 `Depends(require_permission("user:list"))` 声明所需权限
- `require_permission` 在 `app/routers/deps.py` 中定义，由 `app/services/rbac_service.py` 按 “用户 → 角色 → 权限” **实时查库**校验，未授权返回 403
- JWT 仅含用户 id，角色与权限每次请求实时读取，改角色或软删除用户即刻生效

角色管理 API：

- `POST /users/assign-role`：为用户分配角色（需 `role:assign`）
- `DELETE /users/{user_id}/roles/{role_name}`：移除用户角色（需 `role:assign`）

## API 一览与调用示例

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/auth/register` | 注册（默认分配 `user` 角色，201） |
| `POST` | `/auth/login` | OAuth2 表单登录（`username` = 邮箱），返回双 Token |
| `POST` | `/auth/refresh` | 用 Refresh Token 刷新并轮换令牌对 |
| `POST` | `/auth/logout` | 登出，撤销当前 Access Token（可带 `refresh_token`） |
| `GET` | `/users/me` | 当前用户信息 |
| `PUT` | `/users/me` | 更新当前用户资料（仅 `full_name`） |
| `GET` | `/users` | 用户列表，分页 + 可选按启用状态过滤（需 `user:list`） |
| `POST` | `/users/assign-role` | 分配角色（需 `role:assign`） |
| `DELETE` | `/users/{user_id}/roles/{role_name}` | 移除角色（需 `role:assign`） |
| `DELETE` | `/users/{user_id}` | 软删除用户（需 `user:delete`） |

**`GET /users` 的分页与过滤**：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `limit` | `20` | 每页条数，范围 1–100（越界返回 422，避免一次拉走全表） |
| `offset` | `0` | 偏移量，必须 ≥ 0 |
| `is_active` | 不传 | 不传返回全部（含已停用）；传 `true` / `false` 按启用状态过滤 |

响应为分页外壳 `{ items, total, limit, offset }`，`total` 是满足条件的总数，便于前端算页数。

**为什么默认不过滤已停用用户**：这是管理端接口，停用（软删除）的目的是保留数据以便审计和
恢复。如果默认把停用账号藏起来，管理员"删除"之后就再也看不到它，也就无法恢复——那和物理
删除没有区别了。需要只看启用用户时显式传 `is_active=true` 即可。

普通用户流程示例：

```bash
# 注册
curl -s -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email": "alice@example.com", "password": "secret123", "full_name": "Alice"}'

# 登录（OAuth2 密码表单，返回 access_token 与 refresh_token）
curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=alice@example.com&password=secret123'

# 把上一步返回的令牌填入变量（也可用 jq 自动提取）
export ACCESS_TOKEN='<access_token>'
export REFRESH_TOKEN='<refresh_token>'

# 携带 Access Token 访问受保护接口
curl -s http://localhost:8000/users/me \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# 刷新令牌对（旧 Refresh Token 随即失效）
curl -s -X POST http://localhost:8000/auth/refresh \
  -H 'Content-Type: application/json' \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"

# 登出（撤销 Access Token，并可选一并撤销 Refresh Token）
curl -s -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"
```

管理员操作示例（需先注册/登录具备 `admin` 角色的账号）：

```bash
# 为用户分配 admin 角色（需 role:assign）
curl -s -X POST http://localhost:8000/users/assign-role \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "<用户 UUID>", "role_name": "admin"}'
```

## 数据库迁移（Alembic）

开发环境启动时自动建表并写入种子数据；**生产环境请使用 Alembic** 管理数据库结构，迁移脚本位于 `alembic/versions/`：

```bash
alembic upgrade head    # 应用全部迁移到最新版本
alembic revision --autogenerate -m "describe the change"  # 按模型差异生成迁移（需可连接的数据库）
alembic downgrade -1    # 回滚最近一次迁移
alembic history         # 查看迁移历史
alembic current         # 查看当前版本
```

Alembic 连接串通过 `app/config.py` 从 `.env` 的 `DATABASE_URL` 注入（见 `alembic/env.py`），无需单独维护 `alembic.ini` 中的数据库地址。

## 项目结构与架构

项目按 **routers（HTTP）/ schemas（DTO）/ services（业务）/ models（ORM）** 分层，依赖方向自上而下单向：

```text
HTTP 请求（携带 Authorization: Bearer <access_token>）
   │
   ▼
routers/   HTTP 层：参数解析、鉴权依赖、状态码、异常映射
   │  deps.py       get_current_user / require_permission
   │  auth.py       注册、登录、刷新、登出
   │  users.py      当前用户资料与用户管理
   │
   ▼ 调用 services，业务异常 → HTTPException
schemas/   Pydantic 层：请求/响应 DTO 与校验（不含业务逻辑）
   │
   ▼
services/  业务层：用例编排、业务规则、事务边界
   │  auth_service.py    注册 / 登录 / 令牌轮换 / 登出
   │  user_service.py    用户 CRUD / 角色分配 / 软删除
   │  token_service.py   JWT 签发 / 解码 / 撤销
   │  rbac_service.py    权限判定 / 幂等种子数据
   │  errors.py          业务异常定义
   │
   ▼ 通过 SQLAlchemy 异步会话访问数据
models/    ORM 层：表结构与关系
   │  user.py / role.py / permission.py / associations.py
   │
   ▼
database.py（engine / session）+ core/（security、redis 基础设施）
```

分层规则：

- **routers** 只做 HTTP 翻译：解析/构造 `schemas` DTO、声明 `Depends` 鉴权、调用 `services`，并把业务异常映射为 `HTTPException`，不写 SQL
- **schemas** 只做数据校验与序列化，不含业务逻辑
- **services** 承载业务规则（邮箱唯一、默认角色、刷新轮换、软删除等），不感知 `Request` / `Response` / `HTTPException`
- **models** 只定义表结构与关系
- 依赖只允许 “上层 → 下层”，禁止反向引用；`services` 之间可互相调用（如 `auth_service` → `user_service`）

目录结构：

```text
.
├── app/
│   ├── main.py            应用入口：注册路由、启动建表 + RBAC 种子
│   ├── config.py          pydantic-settings 配置（读取 .env / 环境变量）
│   ├── database.py        异步 engine、会话与 get_db 依赖
│   ├── core/              基础设施：security.py（密码哈希）、redis.py（黑名单）
│   ├── models/            SQLAlchemy 模型：user / role / permission / associations
│   ├── schemas/           Pydantic DTO：auth / user / role
│   ├── routers/           API 路由与鉴权依赖（deps.py）
│   └── services/          业务逻辑：auth / user / token / rbac + errors
├── alembic/               数据库迁移（versions/ 存放迁移脚本）
├── tests/                 pytest 集成测试（aiosqlite + fakeredis）
├── Dockerfile             生产镜像（启动时自动 alembic upgrade head）
├── docker-compose.yml     app + MySQL 8.4 + Redis 7
├── requirements.txt       运行时依赖
└── requirements-dev.txt   开发与测试依赖
```

## 运行测试

测试基于 `pytest-asyncio` 与 `httpx.AsyncClient`：每个用例创建独立的内存 SQLite 数据库（`aiosqlite`），用 `fakeredis` 替代真实 Redis，结束后自动清理、互不影响，**无需启动 MySQL 或 Redis**。

```bash
# 安装依赖（已包含测试依赖）
pip install -r requirements-dev.txt

# 运行全部测试
pytest -v
```

说明：`tests/conftest.py` 通过 `app.dependency_overrides` 将应用的 `get_db` / `get_redis` 依赖分别覆盖为测试库连接与 `fakeredis`。
