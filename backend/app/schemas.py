from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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

    items: list[TransactionRead]
    total: int 
    page: int 
    size: int 