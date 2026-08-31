<script setup lang="ts">
import { computed } from 'vue'
import { useCandidatesStore } from '../stores/candidates'
import { DEPARTMENTS, NODE_LABELS } from '../types'

const store = useCandidatesStore()

function pendingCount(nodeType: string) {
  return store.candidates.filter(c => {
    const node = c.nodes.find(n => n.node_type === nodeType)
    return node && (node.status === 'pending' || node.status === 'in_progress')
  }).length
}

const deptItems = computed(() =>
  DEPARTMENTS.map(dept => ({
    ...dept,
    nodeLabel: NODE_LABELS[dept.nodeType] ?? dept.nodeType,
    pending: pendingCount(dept.nodeType),
  }))
)
</script>

<template>
  <aside class="dept-sidebar">
    <div class="sidebar-title">部门视图</div>
    <button
      v-for="dept in deptItems"
      :key="dept.key"
      :class="['dept-item', { active: store.currentDepartment === dept.key }]"
      @click="store.setDepartment(dept.key)"
    >
      <span class="dept-icon">{{ dept.icon }}</span>
      <div class="dept-info">
        <span class="dept-name">{{ dept.label }}</span>
        <span class="dept-hint">{{ dept.nodeLabel }}</span>
      </div>
      <span v-if="dept.pending > 0" class="dept-badge">{{ dept.pending }}</span>
    </button>
  </aside>
</template>

<style scoped>
.dept-sidebar {
  display: flex;
  flex-direction: column;
  width: 220px;
  min-width: 220px;
  background: white;
  border-right: 1px solid #e0e0e0;
  padding: 16px 12px;
  gap: 4px;
}

.sidebar-title {
  font-size: 11px;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 1px;
  padding: 0 8px 8px;
}

.dept-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 12px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s;
}

.dept-item:hover {
  background: #f5f5f5;
}

.dept-item.active {
  background: #e3f2fd;
  box-shadow: inset 3px 0 0 #2196f3;
}

.dept-icon {
  font-size: 22px;
  flex-shrink: 0;
}

.dept-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.dept-name {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a1a;
}

.dept-hint {
  font-size: 11px;
  color: #888;
}

.dept-badge {
  flex-shrink: 0;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: #ff9800;
  color: white;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
