<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Candidate } from '../types'
import { NODE_LABELS, STATUS_COLORS, STATUS_LABELS } from '../types'
import NodeStatus from './NodeStatus.vue'
import { useCandidatesStore } from '../stores/candidates'

const NODE_ORDER = ['contract', 'account', 'device', 'training', 'buddy'] as const

const props = defineProps<{
  candidate: Candidate
}>()

const store = useCandidatesStore()
const editing = ref(false)
const editName = ref('')
const editRole = ref('')
const editSalary = ref('')

const isHrView = computed(() => store.currentDepartment === 'hr')
const currentNodeType = computed(() => store.currentDeptConfig.nodeType)

const currentNode = computed(() =>
  props.candidate.nodes.find(n => n.node_type === currentNodeType.value) ?? null
)

function handleNodeUpdate(status: string, data?: Record<string, any>) {
  if (!currentNode.value) return
  store.updatePrepNode(props.candidate.id, currentNode.value.node_type, status, data)
}

function startEditCandidate() {
  editName.value = props.candidate.name
  editRole.value = props.candidate.role
  editSalary.value = props.candidate.salary
  editing.value = true
}

function cancelEdit() { editing.value = false }

function saveCandidate() {
  store.updateCandidate(props.candidate.id, {
    name: editName.value.trim(),
    role: editRole.value.trim(),
    salary: editSalary.value.trim(),
  })
  editing.value = false
}

const nodeDots = computed(() =>
  NODE_ORDER.map(type => {
    const node = props.candidate.nodes.find(n => n.node_type === type)
    const status = node?.status ?? 'pending'
    return {
      type,
      label: NODE_LABELS[type] ?? type,
      status,
      statusLabel: STATUS_LABELS[status] ?? status,
      color: STATUS_COLORS[status] ?? '#9e9e9e',
      current: type === currentNodeType.value,
    }
  })
)
</script>

<template>
  <div class="candidate-card">
    <div class="card-header">
      <div class="candidate-info" v-if="!editing || !isHrView">
        <span class="candidate-name">{{ candidate.name }}</span>
        <span class="candidate-role">{{ candidate.role }}</span>
        <span class="candidate-pinyin">{{ candidate.pinyin }}</span>
      </div>
      <div class="candidate-info editing" v-else>
        <input v-model="editName" class="edit-name" placeholder="姓名" />
        <input v-model="editRole" class="edit-role" placeholder="岗位" />
      </div>

      <div class="candidate-meta" v-if="!editing || !isHrView">
        <span class="salary">{{ candidate.salary }}</span>
        <div class="node-dots" aria-label="五部门节点状态">
          <span
            v-for="dot in nodeDots"
            :key="dot.type"
            class="node-dot"
            :class="{ current: dot.current }"
            :style="{ background: dot.color }"
            :title="`${dot.label}：${dot.statusLabel}`"
          />
        </div>
        <span v-if="candidate.status === 'cancelled'" class="status-badge cancelled">已取消</span>
        <button
          v-if="isHrView"
          class="btn-edit-candidate"
          @click="startEditCandidate"
          title="编辑基本信息"
        >✏️</button>
      </div>
      <div class="candidate-meta editing" v-else>
        <input v-model="editSalary" class="edit-salary" placeholder="薪资" />
        <div class="edit-meta-actions">
          <button class="btn-sm btn-cancel" @click="cancelEdit">取消</button>
          <button class="btn-sm btn-save" @click="saveCandidate">保存</button>
        </div>
      </div>
    </div>

    <div class="section-label">{{ store.currentDeptConfig.label }} · 入职节点</div>
    <div class="node-area" v-if="currentNode">
      <NodeStatus
        :node="currentNode"
        :editable="true"
        @update="handleNodeUpdate"
      />
    </div>
    <div v-else class="node-missing">该候选人暂无此部门节点</div>
  </div>
</template>

<style scoped>
.candidate-card {
  background: white;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  border: 1px solid #e8e8e8;
  transition: box-shadow 0.2s;
}

.candidate-card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.candidate-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.candidate-info.editing {
  gap: 6px;
}

.candidate-name {
  font-size: 18px;
  font-weight: 700;
  color: #1a1a1a;
}

.candidate-role {
  font-size: 13px;
  color: #888;
}

.candidate-pinyin {
  font-size: 11px;
  color: #bbb;
  font-family: monospace;
}

.candidate-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.candidate-meta.editing {
  gap: 8px;
}

.salary {
  font-size: 14px;
  font-weight: 600;
  color: #e65100;
}

.btn-edit-candidate {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  padding: 2px;
  opacity: 0.5;
  transition: opacity 0.2s;
}

.btn-edit-candidate:hover { opacity: 1; }

.edit-name, .edit-role, .edit-salary {
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  outline: none;
}

.edit-name { font-size: 16px; font-weight: 700; }
.edit-salary { width: 80px; text-align: right; }

.edit-meta-actions {
  display: flex;
  gap: 4px;
}

.btn-sm {
  padding: 3px 8px;
  border: none;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}

.btn-cancel { background: #f5f5f5; color: #666; }
.btn-save { background: #2196f3; color: white; }

.node-dots {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 2px 0;
}

.node-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
}

.node-dot.current {
  outline: 2px solid #1565c0;
  outline-offset: 2px;
}

.status-badge.cancelled {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
  background: #ffebee;
  color: #c62828;
}

.section-label {
  font-size: 12px;
  color: #aaa;
  margin: 10px 0 6px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.node-area {
  display: flex;
}

.node-area :deep(.node-card) {
  flex: 1;
  width: 100%;
}

.node-missing {
  padding: 12px;
  color: #999;
  font-size: 13px;
  background: #fafafa;
  border-radius: 8px;
}
</style>
