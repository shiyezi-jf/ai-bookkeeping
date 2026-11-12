from fastapi import APIRouter, Depends, status, Query, HTTPException

from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Transaction
from app.schemas import TransactionCreate, TransactionRead, TransactionsPage, TransactionUpdate
from app.periods import month_range

from datetime import date




router = APIRouter(prefix="/api/transactions", tags=["transactions"])



@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    payload: TransactionCreate,
    db: AsyncSession = Depends(get_db),
):
    #  1：把 Pydantic 的 payload 翻译成 ORM 对象
    tx = Transaction(**payload.model_dump())

    #  2：加入 session
    db.add(tx)

    #  3：提交事务
    await db.commit()

    #  4：返回新建的对象，FastAPI 会用 TransactionRead 打包
    return tx

@router.get("", response_model=TransactionsPage)
async def list_transactions(
    page: int = Query(default=1, ge=1),
    size: int = Query(10, ge=1, le=100),
    month: str | None = Query(None),
    db: AsyncSession = Depends(get_db)
):

    conds = []
    if month is not None:
        start, end = month_range(month)
        conds.append(Transaction.occurred_on >= start)
        conds.append(Transaction.occurred_on < end)

    count_stmt = select(func.count()).select_from(Transaction)

    data_stmt = select(Transaction)
    if conds:
        count_stmt = count_stmt.where(*conds)
        data_stmt = data_stmt.where(*conds)
    
    total = await db.scalar(count_stmt)

    #  5：查询全部账单，按消费日期从新到旧排序
    # 日期相同再按 id 倒序，保证顺序稳定

    result = await db.execute(
        data_stmt.order_by(
            Transaction.occurred_on.desc(),
            Transaction.id.desc(),
        )
        .limit(size)
        .offset((page - 1) * size)
    )
    
    rows = result.scalars().all()

    #  6：从结果里取出 ORM 对象列表
    return TransactionsPage(
        items=rows,
        total=total,
        page=page,
        size=size
    )

# 部分更新
@router.patch("/{id}", response_model=TransactionRead)
async def update_transactions(
    id: int,
    payload: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
):
    # 1. 找出来
    tx = await db.get(Transaction, id)
    if tx is None:
        raise HTTPException(status_code=404, detail="账单不存在")
    
    # 2. 只改传了的字段
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(tx, field, value)
    
    await db.commit()
    return tx



# 删除功能
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    id: int,
    db: AsyncSession = Depends(get_db)
):
    tx = await db.get(Transaction, id)
    if tx is None:
        raise HTTPException(status_code=404, detail="账单不存在")

    await db.delete(tx)
    await db.commit()
    
