<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { PrepNode } from '../types'
import { STATUS_COLORS, STATUS_LABELS, NODE_LABELS } from '../types'

const props = defineProps<{
  node: PrepNode
  editable: boolean
}>()

const emit = defineEmits<{
  update: [status: string, data?: Record<string, any>]
}>()

const color = computed(() => STATUS_COLORS[props.node.status] ?? '#9e9e9e')
const label = computed(() => STATUS_LABELS[props.node.status] ?? props.node.status)
const nodeLabel = computed(() => NODE_LABELS[props.node.node_type] ?? props.node.node_type)

const statusIcon = computed(() => {
  switch (props.node.status) {
    case 'completed': return '✅'
    case 'in_progress': return '🔵'
    case 'paused': return '🟡'
    case 'rejected': return '🔴'
    default: return '⚪'
  }
})

// Editable fields — filtered data entries
const EDITABLE_KEYS: Record<string, string[]> = {
  contract: ['contract', 'files', 'probation', 'salary'],
  account: ['workno', 'email', 'wecom', 'vpn'],
  device: ['laptop', 'badge', 'desk'],
  training: ['course', 'date', 'content'],
  buddy: ['buddy', 'mentor'],
}

const dataEntries = computed(() => {
  if (!props.node.data || typeof props.node.data !== 'object') return []
  return Object.entries(props.node.data).filter(
    ([k]) => !['system', 'candidate', 'status', 'prepared_at', 'updated_at'].includes(k)
  )
})

const editableKeys = computed(() => EDITABLE_KEYS[props.node.node_type] ?? [])

const editData = ref<Record<string, string>>({})
const editStatus = ref(props.node.status)
const showForm = ref(false)

// Sync editData when node data changes
watch(() => props.node.data, (d) => {
  if (d) {
    const entries: Record<string, string> = {}
    for (const k of editableKeys.value) {
      entries[k] = String(d[k] ?? '')
    }
    editData.value = entries
  }
}, { immediate: true })

function startEdit() {
  editStatus.value = props.node.status
  showForm.value = true
}

function cancelEdit() {
  showForm.value = false
  // Reset to original
  const d = props.node.data
  for (const k of editableKeys.value) {
    editData.value[k] = String(d?.[k] ?? '')
  }
}

function saveData() {
  emit('update', editStatus.value, { ...props.node.data, ...editData.value })
  showForm.value = false
}

function changeStatus(newStatus: string) {
  emit('update', newStatus, props.node.data)
}

function fieldLabel(key: string): string {
  const labels: Record<string, string> = {
    contract: '合同内容', files: '附件文件', probation: '试用期', salary: '薪资',
    workno: '工号', email: '企业邮箱', wecom: '企业微信', vpn: 'VPN',
    laptop: '笔记本电脑', badge: '门禁卡', desk: '工位',
    course: '培训课程', date: '培训时间', content: '培训内容',
    buddy: 'Buddy', mentor: '导师',
  }
  return labels[key] ?? key
}
</script>

<template>
  <div :class="['node-card', { editable, expanded: showForm }]" :style="{ borderColor: color }">
    <div class="node-header">
      <span class="node-icon">{{ statusIcon }}</span>
      <span class="node-name">{{ nodeLabel }}</span>
      <span class="node-status" :style="{ color }">{{ label }}</span>
    </div>

    <!-- Read-only data display -->
    <div class="node-data" v-if="!showForm && dataEntries.length">
      <div v-for="[key, val] in dataEntries" :key="key" class="data-row">
        <span class="data-key">{{ fieldLabel(key) }}:</span>
        <span class="data-val">{{ val }}</span>
      </div>
    </div>

    <!-- Edit form -->
    <div class="node-edit" v-if="showForm">
      <div class="edit-field">
        <label class="edit-label">状态</label>
        <select class="edit-select" v-model="editStatus">
          <option value="pending">⚪ 未开始</option>
          <option value="in_progress">🔵 进行中</option>
          <option value="paused">🟡 暂停</option>
          <option value="completed">🟢 已完成</option>
          <option value="rejected">🔴 否决</option>
        </select>
      </div>
      <div v-for="key in editableKeys" :key="key" class="edit-field">
        <label class="edit-label">{{ fieldLabel(key) }}</label>
        <input
          class="edit-input"
          v-model="editData[key]"
          :placeholder="'请输入' + fieldLabel(key)"
        />
      </div>
      <div class="edit-actions">
        <button class="btn btn-cancel" @click="cancelEdit">取消</button>
        <button class="btn btn-save" @click="saveData">保存</button>
      </div>
    </div>

    <!-- Actions -->
    <div class="node-actions" v-if="editable">
      <button v-if="!showForm" class="btn btn-edit" @click="startEdit">
        ✏️ 编辑
      </button>
      <template v-if="!showForm">
        <select
          class="status-select"
          :value="node.status"
          @change="changeStatus(($event.target as HTMLSelectElement).value)"
        >
          <option value="pending">⚪ 未开始</option>
          <option value="in_progress">🔵 进行中</option>
          <option value="paused">🟡 暂停</option>
          <option value="completed">🟢 已完成</option>
          <option value="rejected">🔴 否决</option>
        </select>
      </template>
    </div>
  </div>
</template>

<style scoped>
.node-card {
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  padding: 12px;
  background: white;
  min-width: 180px;
  transition: all 0.2s;
}

.node-card.editable { cursor: pointer; }
.node-card.editable:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.15); }
.node-card.expanded { min-width: 280px; }

.node-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.node-name { font-weight: 600; font-size: 13px; flex: 1; }
.node-status { font-size: 12px; font-weight: 500; }

.node-data {
  font-size: 12px;
  color: #666;
  border-top: 1px solid #f0f0f0;
  padding-top: 6px;
}

.data-row { display: flex; gap: 4px; line-height: 1.6; }
.data-key { color: #999; min-width: 60px; }
.data-val { color: #333; word-break: break-all; }

/* Edit form */
.node-edit {
  border-top: 1px solid #f0f0f0;
  padding-top: 8px;
  margin-top: 4px;
}

.edit-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 6px;
}

.edit-label {
  font-size: 11px;
  color: #888;
  font-weight: 500;
}

.edit-input {
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.edit-input:focus { border-color: #2196f3; }

.edit-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  justify-content: flex-end;
}

.node-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.btn {
  padding: 4px 10px;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn:hover { opacity: 0.85; }

.btn-edit { background: #fff3e0; color: #e65100; }
.btn-start { background: #e3f2fd; color: #1565c0; }
.btn-done { background: #e8f5e9; color: #2e7d32; }
.btn-cancel { background: #f5f5f5; color: #666; }
.btn-save { background: #2196f3; color: white; }

.edit-select, .status-select {
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 12px;
  background: white;
  cursor: pointer;
  outline: none;
}

.edit-select:focus, .status-select:focus { border-color: #2196f3; }
</style>
