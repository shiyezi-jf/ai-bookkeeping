from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# 1：创建 engine

engine = create_async_engine(settings.database_url, echo=False)  # 写好后把 None 换掉

#  2：创建 session 工厂

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)  

#  3：写 get_db 依赖（大约 3 行）
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session