<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import axios from 'axios'

type Row = Record<string, string | number>

interface MonthlyPayload {
  month: string
  source: string
  status?: string
  editable?: boolean
  metric_version?: string
  report_run_id?: string
  frozen_at?: string
  data_as_of?: string
  updated_at?: string
  recruitment_funnel: Row[]
  positions_progress: Row[]
  onboarding_retention: Row[]
  training_completion: Row[]
  hiring_cost: Row[]
  attrition: Row[]
}

const THEME_KEYS = [
  { key: 'recruitment_funnel', title: '招聘漏斗', monthly: true },
  { key: 'positions_progress', title: '岗位进度', monthly: false },
  { key: 'onboarding_retention', title: '入职留存', monthly: true },
  { key: 'training_completion', title: '培训完成', monthly: true },
  { key: 'hiring_cost', title: '招聘成本', monthly: true },
  { key: 'attrition', title: '离职', monthly: true },
] as const

const months = ref<string[]>([])
const selectedMonth = ref('2026-07')
const payload = ref<MonthlyPayload | null>(null)
const freezing = ref(false)
const saving = ref(false)
const loading = ref(false)
const error = ref('')
const notice = ref('')

const editable = computed(() => !!payload.value?.editable)

const tables = computed(() => {
  const p = payload.value
  if (!p) return []
  return THEME_KEYS.map((t) => ({
    ...t,
    rows: (p[t.key] as Row[]) || [],
  }))
})

function headersOf(rows: Row[]): string[] {
  return rows.length ? Object.keys(rows[0]) : []
}

function isHighlight(monthly: boolean, row: Row): boolean {
  return monthly && String(row['月份'] ?? '') === selectedMonth.value
}

async function fetchMonths() {
  const { data } = await axios.get<{ months: string[] }>('/api/reports/monthly')
  months.value = data.months || []
}

async function fetchMonth(month: string) {
  if (!month) {
    payload.value = null
    return
  }
  loading.value = true
  error.value = ''
  try {
    const { data } = await axios.get<MonthlyPayload>(`/api/reports/monthly/${month}/working`)
    payload.value = data
  } catch (e: any) {
    payload.value = null
    error.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function saveNow() {
  if (!payload.value || !editable.value) return
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    const { data } = await axios.put<MonthlyPayload>(
      `/api/reports/monthly/${selectedMonth.value}/working`,
      {
        recruitment_funnel: payload.value.recruitment_funnel,
        positions_progress: payload.value.positions_progress,
        onboarding_retention: payload.value.onboarding_retention,
        training_completion: payload.value.training_completion,
        hiring_cost: payload.value.hiring_cost,
        attrition: payload.value.attrition,
      },
    )
    payload.value = data
    notice.value = '已保存工作稿'
    await fetchMonths()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    error.value = typeof detail === 'string' ? detail : (e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function addRow(theme: typeof THEME_KEYS[number]['key']) {
  const p = payload.value
  if (!p || !editable.value) return
  const rows = p[theme] as Row[]
  const headers = headersOf(rows)
  const next: Row = {}
  for (const h of headers) {
    next[h] = h === '月份' ? selectedMonth.value : ''
  }
  rows.push(next)
}

function removeRow(theme: typeof THEME_KEYS[number]['key'], index: number) {
  const p = payload.value
  if (!p || !editable.value) return
  const rows = p[theme] as Row[]
  if (rows.length <= 1) return
  rows.splice(index, 1)
}

async function freezeNow() {
  freezing.value = true
  error.value = ''
  notice.value = ''
  try {
    if (editable.value && payload.value) {
      await axios.put(`/api/reports/monthly/${selectedMonth.value}/working`, {
        recruitment_funnel: payload.value.recruitment_funnel,
        positions_progress: payload.value.positions_progress,
        onboarding_retention: payload.value.onboarding_retention,
        training_completion: payload.value.training_completion,
        hiring_cost: payload.value.hiring_cost,
        attrition: payload.value.attrition,
      })
    }
    const { data } = await axios.post<MonthlyPayload>(
      `/api/reports/monthly/${selectedMonth.value}/freeze`,
    )
    payload.value = data
    notice.value = '已冻结，此后只读'
    await fetchMonths()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    error.value = typeof detail === 'string' ? detail : (e?.message || '冻结失败')
  } finally {
    freezing.value = false
  }
}

async function reload() {
  error.value = ''
  notice.value = ''
  try {
    await fetchMonths()
    await fetchMonth(selectedMonth.value)
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    error.value = typeof detail === 'string' ? detail : (e?.message || '加载失败')
  }
}

onMounted(reload)
watch(selectedMonth, (m) => {
  fetchMonth(m)
})

defineExpose({ reload })
</script>

<template>
  <div class="monthly-page">
    <p class="lead">
      未冻结月份可以改表、保存工作稿；冻结后只读，供出报使用。
      入职看板仍是花名册 + 五部门准备节点。
    </p>

    <div class="toolbar">
      <label>
        月份
        <input v-model="selectedMonth" placeholder="YYYY-MM" />
      </label>
      <label v-if="months.length">
        已有月份
        <select v-model="selectedMonth">
          <option v-for="m in months" :key="m" :value="m">{{ m }}</option>
        </select>
      </label>
      <button type="button" class="reload-btn" :disabled="!editable || saving" @click="saveNow">
        {{ saving ? '保存中...' : '保存' }}
      </button>
      <button type="button" class="reload-btn" :disabled="freezing" @click="freezeNow">
        {{ freezing ? '冻结中...' : '冻结该月' }}
      </button>
      <button type="button" class="reload-btn" @click="reload">刷新</button>
    </div>
    <p v-if="payload" class="meta">
      状态={{ payload.status || '—' }}
      <span v-if="payload.report_run_id"> · run={{ payload.report_run_id }}</span>
      <span v-if="payload.frozen_at"> · frozen_at={{ payload.frozen_at }}</span>
      <span v-if="payload.updated_at"> · 工作稿={{ payload.updated_at }}</span>
    </p>
    <p v-if="notice" class="meta ok">{{ notice }}</p>

    <div v-if="loading" class="hint">加载中...</div>
    <div v-else-if="error" class="hint error">{{ error }}</div>

    <section v-for="block in tables" :key="block.key" class="table-block">
      <h2>
        {{ block.title }}
        <button v-if="editable" type="button" class="row-btn" @click="addRow(block.key)">加一行</button>
      </h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th v-for="h in headersOf(block.rows)" :key="h">{{ h }}</th>
              <th v-if="editable"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, i) in block.rows"
              :key="i"
              :class="{ highlight: isHighlight(block.monthly, row) }"
            >
              <td v-for="h in headersOf(block.rows)" :key="h">
                <input
                  v-if="editable"
                  v-model="row[h]"
                  class="cell"
                />
                <template v-else>{{ row[h] }}</template>
              </td>
              <td v-if="editable">
                <button type="button" class="row-btn" @click="removeRow(block.key, i)">删</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.monthly-page {
  max-width: 1100px;
}

.lead {
  font-size: 14px;
  line-height: 1.7;
  color: #555;
  background: #eef6fc;
  border: 1px solid #d0e4f5;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 16px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.toolbar label {
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar select {
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
}

.reload-btn {
  padding: 6px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 13px;
}

.reload-btn:hover:not(:disabled) {
  background: #f5f5f5;
}

.reload-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toolbar input {
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  width: 110px;
}

.meta {
  font-size: 12px;
  color: #666;
  margin: -8px 0 16px;
}

.meta.ok {
  color: #2e7d32;
}

.hint {
  padding: 24px 8px;
  color: #999;
}

.hint.error {
  color: #c62828;
}

.table-block {
  margin-bottom: 24px;
}

.table-block h2 {
  font-size: 15px;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: white;
}

table {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
}

th, td {
  border-bottom: 1px solid #eee;
  padding: 6px 8px;
  text-align: left;
  white-space: nowrap;
}

th {
  background: #f5f8fb;
  font-weight: 600;
}

tr.highlight td {
  background: #fff8e1;
}

.cell {
  width: 92px;
  padding: 4px 6px;
  border: 1px solid #e5e5e5;
  border-radius: 4px;
  font-size: 13px;
}

.row-btn {
  padding: 2px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  font-size: 12px;
}
</style>
