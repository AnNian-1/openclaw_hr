<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Candidate } from '../types'
import { NODE_LABELS, STATUS_COLORS } from '../types'
import NodeStatus from './NodeStatus.vue'
import { useCandidatesStore } from '../stores/candidates'

const props = defineProps<{
  candidate: Candidate
}>()

const store = useCandidatesStore()
const editing = ref(false)
const editName = ref('')
const editRole = ref('')
const editSalary = ref('')

const editableNodeType = computed(() => store.currentDeptConfig.nodeType)

const orderedNodes = computed(() => {
  const order = ['contract', 'account', 'device', 'training', 'buddy']
  return [...props.candidate.nodes].sort((a, b) => order.indexOf(a.node_type) - order.indexOf(b.node_type))
})

const reviews = computed(() => {
  const order = ['day7', 'day30', 'day60', 'day90']
  return [...props.candidate.reviews].sort((a, b) => order.indexOf(a.review_type) - order.indexOf(b.review_type))
})

function handleNodeUpdate(nodeType: string, status: string, data?: Record<string, any>) {
  store.updatePrepNode(props.candidate.id, nodeType, status, data)
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

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    onboarding: '入职中',
    completed: '已完成',
    cancelled: '已取消',
  }
  return map[props.candidate.status] ?? props.candidate.status
})

// ── Review editing ──────────────────────────────
const editingReview = ref<string | null>(null)
const reviewStatus = ref('pending')
const reviewContent = ref('')

const REVIEW_LABELS: Record<string, string> = {
  day7: '7天跟进',
  day30: '30天跟进',
  day60: '60天跟进',
  day90: '90天跟进',
}

function startEditReview(reviewType: string) {
  const r = props.candidate.reviews.find(r => r.review_type === reviewType)
  if (!r) return
  reviewStatus.value = r.status
  reviewContent.value = r.content ?? ''
  editingReview.value = reviewType
}

function saveReview(reviewType: string) {
  store.updateReview(
    props.candidate.id,
    reviewType,
    reviewStatus.value,
    reviewContent.value.trim() || undefined,
  )
  editingReview.value = null
}

function cancelEditReview() {
  editingReview.value = null
}
</script>

<template>
  <div class="candidate-card">
    <div class="card-header">
      <div class="candidate-info" v-if="!editing">
        <span class="candidate-name">{{ candidate.name }}</span>
        <span class="candidate-role">{{ candidate.role }}</span>
        <span class="candidate-pinyin">{{ candidate.pinyin }}</span>
      </div>
      <div class="candidate-info editing" v-else>
        <input v-model="editName" class="edit-name" placeholder="姓名" />
        <input v-model="editRole" class="edit-role" placeholder="岗位" />
      </div>

      <div class="candidate-meta" v-if="!editing">
        <span class="salary">{{ candidate.salary }}</span>
        <span :class="['status-badge', candidate.status]">{{ statusLabel }}</span>
        <button class="btn-edit-candidate" @click="startEditCandidate" title="编辑基本信息">✏️</button>
      </div>
      <div class="candidate-meta editing" v-else>
        <input v-model="editSalary" class="edit-salary" placeholder="薪资" />
        <div class="edit-meta-actions">
          <button class="btn-sm btn-cancel" @click="cancelEdit">取消</button>
          <button class="btn-sm btn-save" @click="saveCandidate">保存</button>
        </div>
      </div>
    </div>

    <div class="section-label">入职准备</div>
    <div class="nodes-row">
      <NodeStatus
        v-for="node in orderedNodes"
        :key="node.node_type"
        :node="node"
        :editable="editableNodeType === node.node_type"
        @update="(status, data) => handleNodeUpdate(node.node_type, status, data)"
      />
    </div>

    <div class="section-label">试用期跟进</div>
    <div class="reviews-row">
      <div
        v-for="review in reviews"
        :key="review.review_type"
        :class="['review-chip', review.status, { editing: editingReview === review.review_type }]"
      >
        <!-- Read-only view -->
        <template v-if="editingReview !== review.review_type">
          <span class="review-type">{{ REVIEW_LABELS[review.review_type] ?? review.review_type }}</span>
          <span class="review-status">{{ review.status === 'completed' ? '✅' : '⚪' }}</span>
          <button class="btn-review-edit" @click.stop="startEditReview(review.review_type)" title="编辑跟进">✏️</button>
        </template>
        <!-- Edit form -->
        <template v-else>
          <div class="review-edit-form">
            <div class="review-edit-row">
              <select class="review-select" v-model="reviewStatus">
                <option value="pending">⚪ 未跟进</option>
                <option value="completed">✅ 已跟进</option>
              </select>
            </div>
            <div class="review-edit-row">
              <textarea
                class="review-textarea"
                v-model="reviewContent"
                placeholder="跟进内容..."
                rows="2"
              ></textarea>
            </div>
            <div class="review-edit-actions">
              <button class="btn-sm btn-cancel" @click="cancelEditReview">取消</button>
              <button class="btn-sm btn-save" @click="saveReview(review.review_type)">保存</button>
            </div>
          </div>
        </template>
      </div>
    </div>
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

.status-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.status-badge.onboarding {
  background: #e3f2fd;
  color: #1565c0;
}

.status-badge.completed {
  background: #e8f5e9;
  color: #2e7d32;
}

.status-badge.cancelled {
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

.nodes-row {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.reviews-row {
  display: flex;
  gap: 8px;
}

.review-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  background: #f5f5f5;
  transition: all 0.2s;
}

.review-chip.completed {
  background: #e8f5e9;
}

.review-chip.editing {
  flex-direction: column;
  align-items: stretch;
  padding: 8px;
  min-width: 200px;
  background: white;
  border: 1px solid #2196f3;
}

.review-type {
  font-weight: 600;
}

.btn-review-edit {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 11px;
  padding: 0 2px;
  opacity: 0;
  transition: opacity 0.2s;
}

.review-chip:hover .btn-review-edit {
  opacity: 0.6;
}

.btn-review-edit:hover {
  opacity: 1 !important;
}

.review-edit-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.review-edit-row {
  display: flex;
  gap: 6px;
}

.review-select {
  flex: 1;
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 12px;
  background: white;
  outline: none;
}

.review-select:focus {
  border-color: #2196f3;
}

.review-textarea {
  width: 100%;
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 12px;
  resize: vertical;
  outline: none;
  font-family: inherit;
  box-sizing: border-box;
}

.review-textarea:focus {
  border-color: #2196f3;
}

.review-edit-actions {
  display: flex;
  gap: 4px;
  justify-content: flex-end;
}
</style>
