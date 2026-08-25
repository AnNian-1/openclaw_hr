<script setup lang="ts">
import { ref } from 'vue'
import { useCandidatesStore } from '../stores/candidates'
import { DEPARTMENTS } from '../types'

const store = useCandidatesStore()
const expanded = ref(false)

const nodeLabel: Record<string, string> = {
  contract: '合同信息',
  account: 'IT账号',
  device: '行政设备',
  training: '培训安排',
  buddy: 'Buddy匹配',
}
</script>

<template>
  <div class="dept-panel">
    <button class="dept-trigger" @click="expanded = !expanded">
      <span class="trigger-icon">{{ store.currentDeptConfig.icon }}</span>
      <span class="trigger-label">{{ store.currentDeptConfig.label }}</span>
      <span class="trigger-arrow" :class="{ open: expanded }">▼</span>
    </button>

    <transition name="slide">
      <div v-if="expanded" class="dept-list">
        <button
          v-for="dept in DEPARTMENTS"
          :key="dept.key"
          :class="['dept-item', { active: store.currentDepartment === dept.key }]"
          @click="store.setDepartment(dept.key); expanded = false"
        >
          <span class="dept-icon">{{ dept.icon }}</span>
          <div class="dept-info">
            <span class="dept-name">{{ dept.label }}</span>
            <span class="dept-hint" v-if="dept.nodeType">
              编辑: {{ nodeLabel[dept.nodeType] ?? dept.nodeType }}
            </span>
            <span class="dept-hint" v-else>全局只读视图</span>
          </div>
          <span v-if="store.currentDepartment === dept.key" class="dept-check">✓</span>
        </button>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.dept-panel {
  position: relative;
  padding: 12px 16px;
  background: #f5f5f5;
  border-bottom: 1px solid #e0e0e0;
}

.dept-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: white;
  cursor: pointer;
  font-size: 14px;
  min-width: 180px;
  transition: all 0.2s;
}

.dept-trigger:hover { border-color: #2196f3; }

.trigger-icon { font-size: 18px; }
.trigger-label { flex: 1; text-align: left; font-weight: 500; }
.trigger-arrow {
  font-size: 10px;
  color: #999;
  transition: transform 0.2s;
}
.trigger-arrow.open { transform: rotate(180deg); }

.dept-list {
  position: absolute;
  top: 100%;
  left: 16px;
  z-index: 100;
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  min-width: 260px;
  overflow: hidden;
}

.dept-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 14px;
  border: none;
  background: white;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s;
  border-bottom: 1px solid #f0f0f0;
}

.dept-item:last-child { border-bottom: none; }
.dept-item:hover { background: #e3f2fd; }
.dept-item.active { background: #e3f2fd; }

.dept-icon { font-size: 20px; }
.dept-info { flex: 1; display: flex; flex-direction: column; gap: 1px; }
.dept-name { font-size: 14px; font-weight: 500; }
.dept-hint { font-size: 11px; color: #999; }
.dept-check { color: #2196f3; font-weight: 700; }

.slide-enter-active, .slide-leave-active { transition: all 0.2s ease; }
.slide-enter-from, .slide-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
