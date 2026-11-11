from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import Base, Category

from app.routers import transactions
from app.routers import parse

@asynccontextmanager
async def lifespan(app: FastAPI):
    #  1：建表（约 2 行）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    #  2：播种分类（只在表为空时）
    async with SessionLocal() as session:
        result = await session.execute(select(Category).limit(1))
        # `scalar_one_or_none()` 才是"取出唯一一行
        if result.scalar_one_or_none() is None:
            session.add_all([
                Category(name="餐饮", icon="food", color="#F97316"),
                Category(name="交通", icon="transport", color="#3B82F6"),
                Category(name="购物", icon="shopping", color="#EC4899"),
                Category(name="居住", icon="home", color="#8B5CF6"),
                Category(name="娱乐", icon="entertainment", color="#F59E0B"),
                Category(name="医疗", icon="medical", color="#EF4444"),
                Category(name="学习", icon="education", color="#10B981"),
                Category(name="其他", icon="other", color="#6B7280"),
            ])
            await session.commit()

    yield

app = FastAPI(title="AI 一句话记账 API", lifespan=lifespan)

app.include_router(transactions.router)
app.include_router(parse.router)

@app.get("/api/ping")
async def ping() -> dict[str, str]:
    return {"message": "pong"}