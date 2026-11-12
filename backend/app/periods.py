from datetime import date

from fastapi import HTTPException

# 工具函数
def month_range(month: str) -> tuple[date, date]:

    # 契约要求严格 YYYY-MM：先卡长度和分隔符位置，再交给 date() 校验数值合法性
    if len(month) != 7 or month[4] != "-":
        raise HTTPException(status_code=400, detail="month 格式必须为 YYYY-MM")

    try:
        year = int(month[:4])
        mon = int(month[5:])

        start = date(year, mon, 1)

        if mon == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, mon + 1, 1)
        return start, end
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="month 格式必须为 YYYY-MM")

def shift_month(month: str, delta: int) -> str:
    """返回 month 平移 delta 个月后的 'YYYY-MM'，自动处理跨年"""
    year = int(month[:4])
    mon = int(month[5:7])

    total = year * 12 + (mon - 1) + delta
    y, m = divmod(total, 12)
    return f"{y:04d}-{m + 1:02d}"

def last_months(month: str, n: int) -> list[str]:
    """返回以 month 结尾的最近 n 个月，从早到晚"""
    return [shift_month(month, -i) for i in range(n - 1, -1, -1)]
    