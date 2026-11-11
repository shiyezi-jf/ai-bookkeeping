import axios from 'axios'

// 所有网络细节都收在这个文件里：前缀、超时、错误翻译
const api = axios.create({
  baseURL: '/api',
  timeout: 30000, // 解析要调大模型，留足 30 秒
})

export type CategoryName =
  | '餐饮'
  | '交通'
  | '购物'
  | '居住'
  | '娱乐'
  | '医疗'
  | '学习'
  | '其他'

/** 模型解析出来的草稿，字段都可能为 null（模型没识别到） */
export interface TransactionDraft {
  amount: string | null // 后端 Decimal 序列化成字符串，如 "68.00"
  category: CategoryName | null
  occurred_on: string | null // YYYY-MM-DD
  note: string | null
  confidence: number // 0 ~ 1
}

export interface ParseResponse {
  draft: TransactionDraft
  fallback: boolean // true = 两次校验都失败，走兜底草稿
  message: string | null
}

export interface TransactionCreate {
  amount: string
  category: CategoryName
  occurred_on: string
  note?: string | null
  raw_text?: string | null
  source?: 'llm' | 'manual'
}

export interface Transaction {
  id: number
  amount: string
  category: string
  occurred_on: string
  note: string | null
  raw_text: string | null
  source: string
  created_at: string
}

/**
 * 把 axios 的各种失败翻译成一句人话。
 * 组件里不用再关心 HTTP 状态码，拿到 message 直接显示。
 */
function toMessage(err: unknown): string {
  if (!axios.isAxiosError(err)) {
    return err instanceof Error ? err.message : '发生未知错误'
  }

  if (err.code === 'ECONNABORTED') return '请求超时，请稍后重试'
  if (!err.response) return '连不上后端，请确认后端已在 8000 端口启动'

  const { status, data } = err.response
  const detail = (data as { detail?: unknown } | undefined)?.detail

  // 500 之类：detail 是一句话
  if (typeof detail === 'string') return detail

  // 422 校验失败：detail 是数组，取第一条拼成「字段: 原因」
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { loc?: unknown[]; msg?: string }
    const field = Array.isArray(first.loc) ? first.loc.slice(1).join('.') : ''
    return field ? `${field}：${first.msg}` : (first.msg ?? '参数校验失败')
  }

  return `请求失败（HTTP ${status}）`
}

/** 统一包一层，失败一律抛 Error，message 已经是可以直接展示的中文 */
async function request<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn()
  } catch (err) {
    throw new Error(toMessage(err))
  }
}

/** 一句话 → 账单草稿（会调大模型，慢且花钱） */
export async function parseText(text: string): Promise<ParseResponse> {
  return request(async () => {
    const { data } = await api.post<ParseResponse>('/parse', { text })
    return data
  })
}

/** 草稿 → 正式账单，落库 */
export async function createTransaction(
  payload: TransactionCreate,
): Promise<Transaction> {
  return request(async () => {
    const { data } = await api.post<Transaction>('/transactions', payload)
    return data
  })
}

/** 查全部账单，后端已按日期倒序 */
export async function listTransactions(): Promise<Transaction[]> {
  return request(async () => {
    const { data } = await api.get<Transaction[]>('/transactions')
    return data
  })
}
