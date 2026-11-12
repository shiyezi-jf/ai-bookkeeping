<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { Category, MonthlyStats } from '../api'

const props = defineProps<{
  stats: MonthlyStats | null
  categories: Category[]
}>()

/** 后端没给 color 时的兜底色，必须和"有颜色"的分类视觉上区分开 */
const FALLBACK_COLOR = '#9CA3AF'

const pieRef = ref<HTMLDivElement | null>(null)
const lineRef = ref<HTMLDivElement | null>(null)

let pie: echarts.ECharts | null = null
let line: echarts.ECharts | null = null

/** 分类名 → 颜色。配色以后端 /api/categories 为准，前端不另存一份常量 */
const colorMap = computed(() => {
  const m = new Map<string, string>()
  for (const c of props.categories) m.set(c.name, c.color ?? FALLBACK_COLOR)
  return m
})

const summary = computed(() => props.stats?.summary ?? [])
const trend = computed(() => props.stats?.trend ?? [])

const hasSummary = computed(() => summary.value.length > 0)
/**
 * 口径（方案 A，已定）：
 * trend 契约恒为 6 条，但 6 个月金额全为 0 时折线只是一条贴底直线，没有信息量，
 * 按"无数据"展示空状态文案，与饼图 summary.length === 0 的判断保持一致。
 * 若将来改为保留贴底直线，把这里换成 trend.value.length > 0 即可。
 */
const hasTrend = computed(() => trend.value.some((t) => Number(t.amount) > 0))

function pieOption(): echarts.EChartsOption {
  return {
    tooltip: {
      trigger: 'item',
      // 与折线图 tooltip 保持同一种写法：先收窄类型，再格式化
      // 不用 '{c}'，那会输出 238 而不是 238.00，与页面其他位置口径不一致
      formatter: (params: unknown) => {
        const p = params as { name: string; value: number; percent: number }
        return `${p.name}<br/>¥${Number(p.value).toFixed(2)}（${Number(p.percent).toFixed(1)}%）`
      },
    },
    legend: {
      bottom: 0,
      type: 'scroll',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: '#4B5563', fontSize: 12 },
    },
    series: [
      {
        type: 'pie',
        // radius[0] = 内半径（中间挖空的圆），radius[1] = 外半径
        // 想从环形改成实心饼：把这一行换成 '65%' 或 ['0%', '65%']
        radius: ['45%', '70%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        label: { show: false },
        labelLine: { show: false },
        emphasis: {
          label: {
            show: true,
            fontSize: 13,
            fontWeight: 'bold',
            formatter: '{b}\n¥{c}',
          },
        },
        data: summary.value.map((s) => ({
          name: s.category,
          // 这里只是把后端给的金额字符串转成图表需要的数值，不做任何金额计算
          value: Number(s.amount),
          itemStyle: { color: colorMap.value.get(s.category) ?? FALLBACK_COLOR },
        })),
      },
    ],
  }
}

function lineOption(): echarts.EChartsOption {
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = (Array.isArray(params) ? params[0] : params) as {
          name: string
          value: number
        }
        return `${p.name}<br/>¥${Number(p.value).toFixed(2)}`
      },
    },
    grid: { left: 58, right: 20, top: 24, bottom: 32 },
    xAxis: {
      type: 'category',
      data: trend.value.map((t) => t.month),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#E5E7EB' } },
      axisLabel: { color: '#9CA3AF', fontSize: 12 },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#9CA3AF', fontSize: 12 },
      splitLine: { lineStyle: { type: 'dashed', color: '#F3F4F6' } },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        symbolSize: 6,
        lineStyle: { width: 2, color: '#2563EB' },
        itemStyle: { color: '#2563EB' },
        areaStyle: { color: 'rgba(37, 99, 235, 0.12)' },
        data: trend.value.map((t) => Number(t.amount)),
      },
    ],
  }
}

/**
 * 统一重绘入口。
 * 第二个参数传 true = notMerge：月份一切换，旧 series 必须整个丢掉，
 * 否则图例会残留上一个月的分类。
 */
function render() {
  if (pie) {
    if (hasSummary.value) pie.setOption(pieOption(), true)
    else pie.clear()
  }
  if (line) {
    if (hasTrend.value) line.setOption(lineOption(), true)
    else line.clear()
  }
}

function handleResize() {
  pie?.resize()
  line?.resize()
}

onMounted(() => {
  if (pieRef.value) pie = echarts.init(pieRef.value)
  if (lineRef.value) line = echarts.init(lineRef.value)
  render()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  pie?.dispose()
  line?.dispose()
  pie = null
  line = null
})

// Home.vue 每次都是整体赋值（stats.value = ...），引用必然变化，浅监听即可
watch(() => props.stats, render)
watch(() => props.categories, render)
</script>

<template>
  <section class="stats">
    <div class="chart-card">
      <h3>分类占比</h3>
      <div class="chart-wrap">
        <div ref="pieRef" class="chart" />
        <p v-if="!hasSummary" class="empty">本月还没有记录</p>
      </div>
    </div>

    <div class="chart-card">
      <h3>近 6 个月趋势</h3>
      <div class="chart-wrap">
        <div ref="lineRef" class="chart" />
        <p v-if="!hasTrend" class="empty">近 6 个月还没有记录</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

@media (max-width: 760px) {
  .stats {
    grid-template-columns: minmax(0, 1fr);
  }
}

.chart-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 16px 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
}

h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-h);
}

.chart-wrap {
  position: relative;
}

.chart {
  width: 100%;
  height: 260px;
}

.empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  font-size: 14px;
  color: #9ca3af;
  pointer-events: none;
}
</style>
