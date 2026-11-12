from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Budget, Category, Transaction
from app.periods import last_months, month_range
from app.schemas import (
    BudgetStat,
    CategoryRead,
    CategoryStat,
    MonthlyStats,
    MonthStat,
)

router = APIRouter(prefix="/api", tags=["stats"])

@router.get("/categories", response_model=list[CategoryRead])
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
      select(Category).order_by(Category.id)
    )
    return result.scalars().all()


@router.get("/stats/monthly", response_model=MonthlyStats)
async def monthly_stats(
    month: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # 没传月份就用当前自然月
    m = month or date.today().strftime("%Y-%m")
    start, end = month_range(m)

    # ① 分类汇总
    rows = await db.execute(
        select(Transaction.category, func.sum(Transaction.amount), func.count())
        .where(Transaction.occurred_on >= start, Transaction.occurred_on < end)
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
    )
    summary = [
        CategoryStat(category=c, amount=a, count=n)
        for c, a, n in rows.all()
    ]

    # ② 近 6 个月趋势
    months = last_months(m, 6)
    trend_start, _ = month_range(months[0])
    month_expr = func.strftime("%Y-%m", Transaction.occurred_on)
    rows = await db.execute(
        select(month_expr, func.sum(Transaction.amount))
        .where(Transaction.occurred_on >= trend_start, Transaction.occurred_on < end)
        .group_by(month_expr)
    )
    by_month = {k: v for k, v in rows.all()}
    trend = [
        MonthStat(month=x, amount=by_month.get(x, Decimal("0")))
        for x in months
    ]

    # ③ 预算
    spent = await db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.occurred_on >= start, Transaction.occurred_on < end)
    )
    b = await db.scalar(
        select(Budget).where(Budget.month == m, Budget.category_id.is_(None))
    )
    budget = None
    if b is not None:
        budget = BudgetStat(amount=b.amount, spent=spent, exceeded=spent > b.amount)

    return MonthlyStats(month=m, summary=summary, trend=trend, budget=budget)
