<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createTransaction,
  deleteTransaction,
  getCategories,
  getMonthlyStats,
  listTransactions,
  parseText,
  updateTransaction,
  type Category,
  type CategoryName,
  type MonthlyStats,
  type Transaction,
  type TransactionCreate,
  type TransactionDraft,
} from '../api'
import StatsCharts from '../components/StatsCharts.vue'

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

// ---- 分页与筛选 ----
const page = ref(1)
const size = ref(10)
/** null = 不筛选月份；有值 = 'YYYY-MM' */
const month = ref<string | null>(null)
const total = ref(0)

// ---- 统计 ----
const stats = ref<MonthlyStats | null>(null)
const statsLoading = ref(false)
const statsError = ref('')
/** 分类字典，饼图配色来自这里 */
const categories = ref<Category[]>([])

// ---- 编辑弹窗 ----
const editVisible = ref(false)
const editSaving = ref(false)
const editError = ref('')
const editId = ref<number | null>(null)
const editForm = ref({
  amount: '',
  category: '' as CategoryName | '',
  occurred_on: '',
  note: '',
})

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

/** 编辑弹窗的校验规则与 D4 确认卡片保持一致：金额 > 0、分类必选、日期必选 */
const canSaveEdit = computed(() => {
  const amount = Number(editForm.value.amount)
  return (
    editForm.value.amount !== '' &&
    Number.isFinite(amount) &&
    amount > 0 &&
    editForm.value.category !== '' &&
    editForm.value.occurred_on !== '' &&
    !editSaving.value
  )
})

const editHint = computed(() => {
  if (editSaving.value) return '保存中…'
  const amount = Number(editForm.value.amount)
  if (editForm.value.amount === '' || !Number.isFinite(amount) || amount <= 0) {
    return '金额必须大于 0'
  }
  if (editForm.value.category === '') return '请选择分类'
  if (editForm.value.occurred_on === '') return '请选择日期'
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
    const res = await listTransactions({
      page: page.value,
      size: size.value,
      month: month.value,
    })
    list.value = res.items
    total.value = res.total
    // 以服务端返回的页码为准：万一本地页码越界，这里能自动纠正
    page.value = res.page
    size.value = res.size
  } catch (e) {
    listError.value = e instanceof Error ? e.message : '列表加载失败'
  } finally {
    listLoading.value = false
  }
}

/** 拉月度统计。month 为 null 时不传，由后端默认当前自然月 */
async function fetchStats() {
  statsLoading.value = true
  statsError.value = ''
  try {
    stats.value = await getMonthlyStats(month.value)
  } catch (e) {
    statsError.value = e instanceof Error ? e.message : '统计加载失败'
  } finally {
    statsLoading.value = false
  }
}

/**
 * 列表与统计一起刷新，互不阻塞。
 * 所有写操作和月份切换都走这里——统计必须跟着数据走，
 * 绝不能在前端拿旧数组自己加减（分页下本地只有 10 条，算出来一定是错的）。
 */
async function refreshAll() {
  await Promise.all([fetchList(), fetchStats()])
}

/** 切月份必须回到第 1 页，否则会停在"第 3 页"却只有 1 页数据 */
function handleMonthChange() {
  page.value = 1
  refreshAll()
}

/** 改每页条数只影响列表分页，统计是按月聚合的，不受 page/size 影响 */
function handleSizeChange() {
  page.value = 1
  fetchList()
}

function openEdit(row: Transaction) {
  editId.value = row.id
  editForm.value = {
    amount: row.amount,
    category: row.category as CategoryName,
    occurred_on: row.occurred_on,
    note: row.note ?? '',
  }
  editError.value = ''
  editVisible.value = true
}

async function handleEditSave() {
  if (!canSaveEdit.value || editId.value === null) return

  editSaving.value = true
  editError.value = ''

  try {
    const note = editForm.value.note.trim()

    await updateTransaction(editId.value, {
      amount: editForm.value.amount, // 原样字符串，全程不碰 float
      category: editForm.value.category as CategoryName,
      occurred_on: editForm.value.occurred_on,
      note: note === '' ? null : note,
    })

    editVisible.value = false
    await refreshAll() // 写操作一律以服务端为准，不手动改本地数组
    ElMessage.success('已保存')
  } catch (e) {
    // 失败时弹窗不关闭，用户填的内容必须留着
    editError.value = e instanceof Error ? e.message : '保存失败，请重试'
  } finally {
    editSaving.value = false
  }
}

async function handleDelete(row: Transaction) {
  try {
    await ElMessageBox.confirm(
      `确定删除 ${row.occurred_on} 的这笔 ¥${row.amount} 吗？删除后不可恢复。`,
      '删除确认',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      },
    )
  } catch {
    return // 用户点了取消，什么都不做
  }

  try {
    await deleteTransaction(row.id)

    // 空页处理：删掉的是本页最后一条，且当前不在第 1 页，就先退一页
    if (list.value.length === 1 && page.value > 1) {
      page.value -= 1
    }

    await refreshAll()
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败，请重试')
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

    // 新记录日期通常是今天，按倒序会排在第 1 页；不回第 1 页用户会以为没存上
    page.value = 1
    await refreshAll()
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

/** 首次进入：先拿分类配色，再并行拉列表和统计 */
async function init() {
  try {
    categories.value = await getCategories()
  } catch {
    // 配色拿不到不影响主流程，饼图会退到统一兜底色
    categories.value = []
  }
  await refreshAll()
}

onMounted(init)
</script>

<template>
  <main class="home">
    <header>
      <h1>AI 一句话记账</h1>
      <p class="hint">用大白话描述这笔消费，比如「昨天打车 25 块」</p>
    </header>

    <!-- 预算提示：没有预算记录时整块不渲染 -->
    <section
      v-if="stats?.budget"
      class="budget"
      :class="{ exceeded: stats.budget.exceeded }"
      role="status"
    >
      <span class="dot" aria-hidden="true" />
      <span v-if="stats.budget.exceeded">
        本月预算 ¥{{ stats.budget.amount }}，已支出 ¥{{ stats.budget.spent }}，已超支
      </span>
      <span v-else>
        本月预算 ¥{{ stats.budget.amount }}，已支出 ¥{{ stats.budget.spent }}
      </span>
    </section>

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
      <div class="list-head">
        <h2>账单</h2>

        <el-date-picker
          v-model="month"
          type="month"
          value-format="YYYY-MM"
          placeholder="全部月份"
          :editable="false"
          clearable
          @change="handleMonthChange"
        />
      </div>

      <p v-if="listError" class="error" role="alert">{{ listError }}</p>

      <el-table
        v-loading="listLoading"
        :data="list"
        empty-text="还没有记录，试着在上面记一笔吧"
        style="width: 100%"
      >
        <el-table-column prop="occurred_on" label="日期" width="118" />
        <el-table-column prop="category" label="分类" width="88" />
        <el-table-column label="备注" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.note ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="金额" width="120" align="right">
          <template #default="{ row }">
            <span class="amt">¥{{ row.amount }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="128" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="total > 0" class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="fetchList"
          @size-change="handleSizeChange"
        />
      </div>
    </section>

    <!-- ⑤ 统计图表：跟随上面的月份筛选 -->
    <p v-if="statsError" class="error" role="alert">{{ statsError }}</p>
    <StatsCharts
      v-if="!statsLoading || stats"
      :stats="stats"
      :categories="categories"
    />
    <p v-else class="muted">统计加载中…</p>

    <!-- ④ 编辑弹窗 -->
    <el-dialog
      v-model="editVisible"
      title="编辑账单"
      width="420px"
      :close-on-click-modal="false"
    >
      <div class="form">
        <label class="field">
          <span>金额</span>
          <el-input v-model="editForm.amount" inputmode="decimal" placeholder="0.00" />
        </label>

        <label class="field">
          <span>分类</span>
          <el-select v-model="editForm.category" placeholder="请选择">
            <el-option v-for="c in CATEGORIES" :key="c" :label="c" :value="c" />
          </el-select>
        </label>

        <label class="field">
          <span>日期</span>
          <el-date-picker
            v-model="editForm.occurred_on"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
          />
        </label>

        <label class="field">
          <span>备注</span>
          <el-input v-model="editForm.note" maxlength="200" placeholder="选填" />
        </label>
      </div>

      <p v-if="editError" class="error" role="alert">{{ editError }}</p>

      <template #footer>
        <div class="dialog-footer">
          <span v-if="!canSaveEdit" class="reason">{{ editHint }}</span>
          <el-button @click="editVisible = false">取消</el-button>
          <el-button
            type="primary"
            :loading="editSaving"
            :disabled="!canSaveEdit"
            @click="handleEditSave"
          >
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>
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

.budget {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-left: 3px solid #9ca3af;
  border-radius: 8px;
  background: #f9fafb;
  font-size: 14px;
  color: #4b5563;
}

.budget .dot {
  flex: 0 0 auto;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #9ca3af;
}

/* 超支用语义红，不用主题蓝 */
.budget.exceeded {
  border-color: #fecaca;
  border-left-color: #dc2626;
  background: #fef2f2;
  color: #dc2626;
}

.budget.exceeded .dot {
  background: #dc2626;
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

/* Element Plus 组件的根节点不会命中上面的原生选择器，单独让它们撑满剩余宽度 */
.field :deep(.el-input),
.field :deep(.el-select),
.field :deep(.el-date-editor) {
  flex: 1;
  min-width: 0;
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

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.pager {
  display: flex;
  justify-content: flex-end;
}

.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}

.amt {
  font-weight: 500;
  color: var(--text-h);
  font-variant-numeric: tabular-nums;
}
</style>
