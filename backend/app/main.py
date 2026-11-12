from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal, engine
from app.models import Base, Category, Budget

from app.routers import transactions, stats
from app.routers import parse

from datetime import date
from decimal import Decimal

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

        current_month = date.today().strftime("%Y-%m")
        exists = await session.scalar(
            select(Budget).where(
                Budget.month == current_month,
                Budget.category_id.is_(None),
            )
        )
        if exists is None:
            session.add(Budget(month=current_month, amount=Decimal("3000.00")))
            await session.commit()

    yield

app = FastAPI(title="AI 一句话记账 API", lifespan=lifespan)

# 本地开发走 Vite proxy 用不到 CORS；线上前后端不同域，必须按来源放行
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions.router)
app.include_router(parse.router)
app.include_router(stats.router)

@app.get("/api/ping")
async def ping() -> dict[str, str]:
    return {"message": "pong"}