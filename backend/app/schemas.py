from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

CategoryName = Literal["餐饮", "交通", "购物", "居住", "娱乐", "医疗", "学习", "其他"]

class TransactionCreate(BaseModel):
    """创建账单时，前端能传的字段"""

    # TODO 1：金额 —— Decimal 类型，必须大于 0，最多 10 位、最多 2 位小数
    # 提示：用 Field(gt=0, max_digits=10, decimal_places=2)
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)

    # TODO 2：分类 —— 只能是预设 8 类之一
    # 提示：用 Literal["餐饮", "交通", "购物", "居住", "娱乐", "医疗", "学习", "其他"]
    # 为什么用 Literal：Swagger 会自动列出可选值，传错值自动 422，不用自己写 if 判断
    category: CategoryName

    # 消费日期 —— 类型注解已经是 date，Pydantic 会自动校验格式
    occurred_on: date

    # 备注 —— 可选，最长 200
    note: str | None = Field(default=None, max_length=200)

    # 原始口语 —— 可选
    raw_text: str | None = None

    # 来源 —— 只能是 llm 或 manual；D2 手动录入默认 manual
    source: Literal["llm", "manual"] = "manual"

class TransactionRead(BaseModel):
    """返回给前端时的字段清单"""

    # TODO 3：允许 Pydantic 直接从 ORM 对象的属性上读值
    # 为什么需要：ORM 对象不是字典，Pydantic 默认不会“按属性”取值
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    amount: Decimal
    category: str
    occurred_on: date
    note: str | None
    raw_text: str | None
    source: str
    created_at: datetime
    
class TransactionDraft(BaseModel):
    """草稿模型"""
    amount: Decimal | None = Field(gt=0, max_digits=10, decimal_places=2, default=None)
    category: CategoryName | None = None
    occurred_on: date | None = None
    note: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    
class ParseRequest(BaseModel):
    """解析请求"""
    text: str = Field(min_length=1, max_length=200)


class ParseResponse(BaseModel):
    """解析响应"""
    draft: TransactionDraft
    fallback: bool = False
    message: str | None = None

class TransactionsPage(BaseModel):
    # 这一页的实际数据
    items: list[TransactionRead]
    # 符合筛选条件的总条数
    total: int 
    # 第几页
    page: int 
    # 每页几条
    size: int 

class TransactionUpdate(BaseModel):
    """编辑账单：所有字段都可选，只传要改的"""

    amount: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    category: CategoryName | None = None
    occurred_on: date | None = None
    note: str | None = Field(default=None, max_length=200)


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    icon: str | None
    color: str | None


# ---- D6 统计相关 ----


class CategoryStat(BaseModel):
    """饼图的一瓣：某个分类在所选月份里的合计"""

    category: str
    amount: Decimal
    count: int

    @field_serializer("amount")
    def _amount_2dp(self, v: Decimal) -> str:
        # 统一输出两位小数字符串，前端拿到就能直接显示，不用再补零
        return f"{v:.2f}"


class MonthStat(BaseModel):
    """折线图上的一个点：某个月的合计。无数据的月份由后端补 0"""

    month: str  # YYYY-MM
    amount: Decimal

    @field_serializer("amount")
    def _amount_2dp(self, v: Decimal) -> str:
        return f"{v:.2f}"


class BudgetStat(BaseModel):
    """所选月份的总预算与已花金额"""

    amount: Decimal
    spent: Decimal
    exceeded: bool

    @field_serializer("amount", "spent")
    def _amount_2dp(self, v: Decimal) -> str:
        return f"{v:.2f}"


class MonthlyStats(BaseModel):
    month: str
    summary: list[CategoryStat]
    trend: list[MonthStat]
    # 该月没有预算记录时为 None，前端据此不展示提示
    budget: BudgetStat | None
