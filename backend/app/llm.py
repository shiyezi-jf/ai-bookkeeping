from datetime import date

from openai import AsyncOpenAI

from app.config import settings

# 客户端在模块顶层创建一次：复用连接，不要每次请求都 new
client = AsyncOpenAI(
    api_key=settings.llm_api_key.get_secret_value(),  # SecretStr 必须拆包，否则发出去的是 **********
    base_url=settings.llm_base_url,
)

def build_system_prompt(today: date) -> str:
    
    return f"""你是一个中文记账解释器。今天是{today.isoformat()}。
    
任务： 从用户的一句话里提取一笔【支出】，不要处理收入。
分类只能从这八个里选：餐饮、交通、购物、居住、娱乐、医疗、学习、其他。
参考：吃饭饮料→餐饮；打车地铁加油→交通；衣服日用品→购物；房租水电→居住；
电影游戏健身等已消遣为目的的支出→娱乐；药品→医疗；书本文具打印→学习；确实沾不上边的才→其他。
分类必须选最接近的一个，不要因为没在例子中列出就归入"其他"

金额规则：只输出数字，不要单位；“12块8”要理解为 12.8。
日期规则：输出 YYYY-MM-DD；“昨天”是今天减 1 天，“前天”减 2 天；没说日期就用今天。
备注规则：不超过 15 个字，概括这笔消费。

如果这句话不是支出（比如工资到账），amount 和 category 都输出 null。
只输出一个 JSON 对象，不要解释，不要 markdown。字段固定为：
{{"amount": 数字或null, "category": "分类或null", "occurred_on": "日期或null", "note": "备注或null", "confidence": 0到1的小数}}
"""  

async def call_llm(user_text: str, error_feedback: str | None = None) -> str:
    
    messages = [
      {"role": "system", "content": build_system_prompt(date.today())},
      {"role": "user", "content": user_text + (f" {error_feedback}" if error_feedback else "")},
    ]
    # 调用大模型接口并接住它
    resp = await client.chat.completions.create(
      model=settings.llm_model,
      messages=messages,
      temperature=0, # 随机性降到最低
      response_format={"type": "json_object"},
    )

    #  4：返回模型输出的文本
    return _clean_json_text(resp.choices[0].message.content or "")

def _clean_json_text(raw: str) -> str:
    
    text = raw.strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.removesuffix("```")

    return text.strip()