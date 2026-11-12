import axios from 'axios'

// 所有网络细节都收在这个文件里：前缀、超时、错误翻译
// 本地开发不配环境变量，默认 '/api' 走 vite.config.ts 的代理；
// 线上在 Vercel 配 VITE_API_BASE_URL，值为后端完整前缀且必须带 /api
const baseURL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '/api'

const api = axios.create({
  baseURL,
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

/** 后端分页响应，与 schemas.TransactionsPage 一一对应 */
export interface TransactionPage {
  items: Transaction[]
  /** 满足筛选条件的总条数，不是当前页条数 */
  total: number
  page: number
  size: number
}

/** 列表查询参数，全部可选 */
export interface ListParams {
  page?: number
  size?: number
  /** 格式 YYYY-MM；不传表示不按月份筛选 */
  month?: string | null
}

/** 编辑时的部分更新体，只传要改的字段 */
export interface TransactionUpdate {
  amount?: string
  category?: CategoryName
  occurred_on?: string
  note?: string | null
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

/**
 * 查账单列表（分页 + 可选月份筛选）。
 *
 * 注意 month 为空时要彻底不传这个 key，不能传空字符串：
 * 传 "" 后端会拿到 month=""，month_range("") 拆不出年月，直接 400。
 * 这里统一在发请求前把空值剔掉，组件里就不用每次都判断。
 */
export async function listTransactions(
  params: ListParams = {},
): Promise<TransactionPage> {
  const query: Record<string, string | number> = {
    page: params.page ?? 1,
    size: params.size ?? 10,
  }
  if (params.month) query.month = params.month

  return request(async () => {
    const { data } = await api.get<TransactionPage>('/transactions', {
      params: query,
    })
    return data
  })
}

/** 部分更新一条账单，返回更新后的完整记录 */
export async function updateTransaction(
  id: number,
  payload: TransactionUpdate,
): Promise<Transaction> {
  return request(async () => {
    const { data } = await api.patch<Transaction>(`/transactions/${id}`, payload)
    return data
  })
}

/** 删除一条账单。后端返回 204 无响应体，所以这里也没有返回值 */
export async function deleteTransaction(id: number): Promise<void> {
  return request(async () => {
    await api.delete(`/transactions/${id}`)
  })
}

// ---- D6 统计相关 ----

/** 分类字典，饼图配色以此为准，前端不写死颜色 */
export interface Category {
  id: number
  name: string
  icon: string | null
  color: string | null
}

export interface CategoryStat {
  category: string
  amount: string // "123.50"
  count: number
}

export interface MonthStat {
  month: string // YYYY-MM
  amount: string
}

export interface BudgetStat {
  amount: string
  spent: string
  exceeded: boolean
}

export interface MonthlyStats {
  month: string
  summary: CategoryStat[]
  trend: MonthStat[]
  /** 该月没有预算记录时为 null */
  budget: BudgetStat | null
}

/** 拉分类字典（含配色） */
export async function getCategories(): Promise<Category[]> {
  return request(async () => {
    const { data } = await api.get<Category[]>('/categories')
    return data
  })
}

/**
 * 拉月度统计。
 * 不传 month 时后端默认当前自然月，所以这里也不发空串。
 */
export async function getMonthlyStats(
  month?: string | null,
): Promise<MonthlyStats> {
  return request(async () => {
    const { data } = await api.get<MonthlyStats>('/stats/monthly', {
      params: month ? { month } : {},
    })
    return data
  })
}

