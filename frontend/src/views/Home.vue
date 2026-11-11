<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  createTransaction,
  listTransactions,
  parseText,
  type CategoryName,
  type Transaction,
  type TransactionCreate,
  type TransactionDraft,
} from '../api'

const CATEGORIES: CategoryName[] = [
  '餐饮',
  '交通',
  '购物',
  '居住',
  '娱乐',
  '医疗',
  '学习',
  '其他',
]

// ---- 解析 ----
const text = ref('')
const loading = ref(false)
const error = ref('')

// draft = 模型的原始答案，保留作证据，不直接绑输入框
const draft = ref<TransactionDraft | null>(null)
const fallback = ref(false)

// form = 用户改完、真正要提交的答案
const form = ref({ amount: '', category: '', occurred_on: '', note: '' })

// ---- 提交 ----
const submitting = ref(false)
const submitError = ref('')

// ---- 列表 ----
const list = ref<Transaction[]>([])
const listLoading = ref(false)
const listError = ref('')

/** 本地日期 YYYY-MM-DD。不能用 toISOString()：那是 UTC，东八区早上 8 点前会拿到昨天 */
function todayStr(): string {
  const d = new Date()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${month}-${day}`
}

const canParse = computed(
  () => text.value.trim().length > 0 && !loading.value && !submitting.value,
)

const canSubmit = computed(() => {
  const amount = Number(form.value.amount)
  return (
    form.value.amount !== '' &&
    Number.isFinite(amount) &&
    amount > 0 &&
    form.value.category !== '' &&
    form.value.occurred_on !== '' &&
    !submitting.value
  )
})

/** canSubmit 为 false 时说清楚为什么，别让用户对着灰按钮猜 */
const submitHint = computed(() => {
  if (submitting.value) return '提交中…'
  if (form.value.amount === '' || Number(form.value.amount) <= 0) return '请先填写金额'
  if (form.value.category === '') return '请先选择分类'
  if (form.value.occurred_on === '') return '请先选择日期'
  return ''
})

async function handleParse() {
  if (!canParse.value) return

  loading.value = true
  error.value = ''
  draft.value = null // 先清空，避免看到上一次的旧结果
  submitError.value = ''

  try {
    const res = await parseText(text.value.trim())
    draft.value = res.draft
    fallback.value = res.fallback

    // draft → form：空值在用户能看懂的地方补上
    form.value = {
      amount: res.draft.amount ?? '',
      category: res.draft.category ?? '',
      occurred_on: res.draft.occurred_on ?? todayStr(), // 日期没识别就默认今天
      note: res.draft.note ?? '',
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '解析失败，请重试'
  } finally {
    // 不管成功失败都要解锁，否则按钮会永远卡在禁用状态
    loading.value = false
  }
}

async function fetchList() {
  listLoading.value = true
  listError.value = ''
  try {
    list.value = await listTransactions()
  } catch (e) {
    listError.value = e instanceof Error ? e.message : '列表加载失败'
  } finally {
    listLoading.value = false
  }
}

async function handleSubmit() {
  if (!canSubmit.value) return

  submitting.value = true
  submitError.value = ''

  try {
    const note = form.value.note.trim()

    const payload: TransactionCreate = {
      amount: form.value.amount, // 原样字符串，不转数字
      category: form.value.category as CategoryName,
      occurred_on: form.value.occurred_on,
      note: note === '' ? null : note, // 空字符串和"没填"是两件事
      raw_text: text.value, // 把 AI 看到的那句话一起存下来
      source: fallback.value ? 'manual' : 'llm',
    }

    await createTransaction(payload)

    // 只有成功才清空；失败时用户填的内容必须留着
    form.value = { amount: '', category: '', occurred_on: '', note: '' }
    draft.value = null
    fallback.value = false
    text.value = ''

    await fetchList()
  } catch (e) {
    submitError.value = e instanceof Error ? e.message : '保存失败，请重试'
  } finally {
    submitting.value = false
  }
}

function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`
}

/**
 * 金额不能用 v-model 绑 type="number"。
 * Vue 3 的 vModelText 里有 `castToNumber = number || type === "number"`，
 * 就算不写 .number，type="number" 也会自动转成 JS number，"12.80" 变成 12.8。
 * 这里手动取 DOM 上的原始字符串，全程不碰数字类型。
 */
function onAmountInput(e: Event) {
  form.value.amount = (e.target as HTMLInputElement).value
}

onMounted(fetchList)
</script>

<template>
  <main class="home">
    <header>
      <h1>AI 一句话记账</h1>
      <p class="hint">用大白话描述这笔消费，比如「昨天打车 25 块」</p>
    </header>

    <!-- ① 输入区 -->
    <section class="card">
      <label class="label" for="input">这笔钱花在哪了？</label>

      <textarea
        id="input"
        v-model="text"
        rows="3"
        maxlength="200"
        placeholder="例如：昨天中午和同事吃火锅，人均 68"
        @keydown.ctrl.enter.prevent="handleParse"
        @keydown.meta.enter.prevent="handleParse"
      />

      <div class="row">
        <span class="counter">{{ text.length }} / 200</span>
        <button type="button" :disabled="!canParse" @click="handleParse">
          <span v-if="loading" class="spinner" aria-hidden="true" />
          {{ loading ? '解析中…' : '解析' }}
        </button>
      </div>

      <p class="tip">Ctrl + Enter 也可以直接解析</p>

      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </section>

    <!-- ② 预览确认 -->
    <section v-if="draft" class="card">
      <p v-if="fallback" class="warn" role="status">
        模型两次输出都不合规，这是兜底草稿，请逐项核对
      </p>

      <div class="form">
        <label class="field">
          <span>金额</span>
          <input
            :value="form.amount"
            type="number"
            step="0.01"
            min="0.01"
            inputmode="decimal"
            placeholder="0.00"
            @input="onAmountInput"
          />
        </label>

        <label class="field">
          <span>分类</span>
          <select v-model="form.category">
            <option value="">请选择</option>
            <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>

        <label class="field">
          <span>日期</span>
          <input v-model="form.occurred_on" type="date" />
        </label>

        <label class="field">
          <span>备注</span>
          <input v-model="form.note" type="text" maxlength="200" placeholder="选填" />
        </label>

        <div class="field readonly">
          <span>置信度</span>
          <strong>{{ formatConfidence(draft.confidence) }}</strong>
        </div>
      </div>

      <div class="actions">
        <button type="button" :disabled="!canSubmit" @click="handleSubmit">
          <span v-if="submitting" class="spinner" aria-hidden="true" />
          {{ submitting ? '保存中…' : '确认记账' }}
        </button>
        <span v-if="!canSubmit" class="reason">{{ submitHint }}</span>
      </div>

      <p v-if="submitError" class="error" role="alert">{{ submitError }}</p>
    </section>

    <!-- ③ 列表 -->
    <section class="card">
      <h2>账单</h2>

      <p v-if="listLoading" class="muted">加载中…</p>
      <p v-else-if="listError" class="error" role="alert">{{ listError }}</p>
      <p v-else-if="list.length === 0" class="muted">还没有记录，试着在上面记一笔吧</p>

      <ul v-else class="list">
        <li v-for="item in list" :key="item.id">
          <span class="date">{{ item.occurred_on }}</span>
          <span class="cat">{{ item.category }}</span>
          <span class="note">{{ item.note ?? '—' }}</span>
          <span class="amt">¥{{ item.amount }}</span>
        </li>
      </ul>
    </section>
  </main>
</template>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

header h1 {
  margin-bottom: 4px;
}

h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: var(--text-h);
}

.hint {
  margin: 0;
  font-size: 14px;
}

.card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
}

.label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-h);
}

textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font: inherit;
  color: var(--text-h);
  resize: vertical;
}

textarea:focus,
input:focus,
select:focus {
  border-color: var(--accent);
  outline: 2px solid rgb(37 99 235 / 0.15);
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.counter,
.tip {
  font-size: 12px;
  color: #9ca3af;
}

.tip {
  margin: 0;
}

button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border: 1px solid var(--accent);
  border-radius: 6px;
  background: var(--accent);
  color: #fff;
  font: inherit;
  font-size: 14px;
  cursor: pointer;
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgb(255 255 255 / 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error {
  margin: 0;
  padding: 8px 12px;
  border-radius: 6px;
  background: #fef2f2;
  font-size: 14px;
  color: #dc2626;
}

.warn {
  margin: 0;
  padding: 8px 12px;
  border-radius: 6px;
  background: #fffbeb;
  font-size: 13px;
  color: #b45309;
}

.muted {
  margin: 0;
  font-size: 14px;
  color: #9ca3af;
}

.form {
  display: grid;
  gap: 10px;
}

.field {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 15px;
}

.field > span {
  flex: 0 0 64px;
  color: #9ca3af;
}

.field input,
.field select {
  flex: 1;
  min-width: 0;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: #fff;
  font: inherit;
  font-size: 15px;
  color: var(--text-h);
}

.field.readonly strong {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-h);
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.reason {
  font-size: 13px;
  color: #9ca3af;
}

.list {
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: 0;
  list-style: none;
}

.list li {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-top: 1px solid var(--border);
  font-size: 15px;
}

.list li:first-child {
  border-top: none;
}

.date {
  flex: 0 0 96px;
  color: #9ca3af;
  font-variant-numeric: tabular-nums;
}

.cat {
  flex: 0 0 56px;
  color: var(--text-h);
}

.note {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  color: var(--text);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.amt {
  flex: 0 0 auto;
  font-weight: 500;
  color: var(--text-h);
  font-variant-numeric: tabular-nums;
}
</style>
