from fastapi import FastAPI

from app.database import AsyncSessionLocal, Base, engine
from app.routers import auth, users
from app.services.rbac_service import seed_rbac

app = FastAPI(
    title="FastAPI User Auth System",
    description="基于 FastAPI 与 MySQL 的用户认证与授权系统",
    version="0.1.0",
)

app.include_router(auth.router)
app.include_router(users.router)


@app.on_event("startup")
async def on_startup() -> None:
    # 开发环境自动建表；生产环境请改用 Alembic 迁移
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await seed_rbac(session)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "FastAPI User Auth System is running"}
