from fastapi import APIRouter, HTTPException
from openai import APIError
from pydantic import ValidationError

from app.llm import call_llm
from app.schemas import ParseRequest, ParseResponse, TransactionDraft

router = APIRouter(prefix="/api", tags=["parse"])

MAX_FEEDBACK_CHARS = 300

def _build_feedback(err: ValidationError) -> str:
    # TODO 3：把 err 变成一句中文提示，例如：
    # "上次输出不合法：<截断后的错误>。请严格按 schema 重新输出，只输出 JSON。"
    # 记得截断到 MAX_FEEDBACK_CHARS
    return f"上次输出不合法：{err.errors()[0].msg}。请严格按 schema 重新输出，只输出 JSON。"

@router.post("/parse", response_model=ParseResponse)
async def parse_text(payload: ParseRequest) -> ParseResponse:
    try:
        # TODO 4：第 1 次调用
        raw = await call_llm(payload.text)

        try:
            # TODO 5：第 1 次校验（try 只包这一行）
            draft = TransactionDraft.model_validate_json(raw)
            return ParseResponse(draft=draft, fallback=False)



        except ValidationError as e:
            feedback = _build_feedback(e)

            # TODO 6：第 2 次调用，把 feedback 一起传进去
            raw2 = await call_llm(payload.text, feedback)

            try:
                # TODO 7：第 2 次校验
                draft = TransactionDraft.model_validate_json(raw2)
                return ParseResponse(draft=draft, fallback=False)
            except ValidationError:
                # TODO 8：两次都失败 → 兜底草稿
                return ParseResponse(draft=TransactionDraft(), fallback=True, message="校验失败")


    except APIError as exc:
        # TODO 10：模型服务本身出问题 → 500，不要兜底
        raise HTTPException(status_code=500, detail="模型服务出错") from exc