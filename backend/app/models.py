from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    """所有表模型的基类；SQLAlchemy 靠它收集所有表"""

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    category: Mapped[str] = mapped_column(String(20), index=True)
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    note: Mapped[str | None] = mapped_column(String(200))
    raw_text: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(20), unique=True)
    icon: Mapped[str | None] = mapped_column(String(20))
    color: Mapped[str | None] = mapped_column(String(10))

class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    #  11：月份 —— 固定 7 位字符串，格式 'YYYY-MM'，不能为空
    # 提示：mapped_column(String(7))
    month: Mapped[str] = mapped_column(String(7))

    #  12：预算金额 —— 定点小数(10,2)，不能为空
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    #  13：分类编号 —— 外键指向 categories.id，可为空
    # 可为空代表“整月总预算”；有值代表“某个分类的专项预算”
    # 提示：mapped_column(ForeignKey("categories.id"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
