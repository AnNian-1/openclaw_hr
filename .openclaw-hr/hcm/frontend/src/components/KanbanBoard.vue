<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useCandidatesStore } from '../stores/candidates'
import { useWebSocket } from '../composables/useWebSocket'
import DepartmentTab from './DepartmentTab.vue'
import CandidateCard from './CandidateCard.vue'
import NewCandidateDialog from './NewCandidateDialog.vue'

const store = useCandidatesStore()
const showNewDialog = ref(false)

onMounted(() => {
  store.fetchCandidates()
})

useWebSocket((evt) => {
  store.handleWSEvent(evt)
})

async function handleCreate(data: { name: string; pinyin: string; role: string; salary: string }) {
  await store.createCandidate(data)
  showNewDialog.value = false
}
</script>

<template>
  <div class="kanban-app">
    <header class="app-header">
      <h1>📋 HCM 入职管理看板</h1>
      <div class="header-meta">
        <span class="dept-label">
          当前视角：{{ store.currentDeptConfig.icon }} {{ store.currentDeptConfig.label }}
        </span>
        <button class="add-btn" @click="showNewDialog = true">➕ 新建候选人</button>
        <button class="refresh-btn" @click="store.fetchCandidates()">🔄 刷新</button>
      </div>
    </header>

    <DepartmentTab />

    <main class="kanban-board">
      <div v-if="store.loading" class="loading">加载中...</div>

      <div v-else-if="store.candidates.length === 0" class="empty">
        暂无候选人数据，请先运行 <code>seed.py</code> 导入数据
      </div>

      <div v-else class="cards-grid">
        <CandidateCard
          v-for="c in store.candidates"
          :key="c.id"
          :candidate="c"
        />
      </div>
    </main>

    <NewCandidateDialog
      v-if="showNewDialog"
      @submit="handleCreate"
      @cancel="showNewDialog = false"
    />
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f0f2f5;
  color: #333;
}
</style>

<style scoped>
.kanban-app {
  min-height: 100vh;
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
}

.app-header h1 {
  font-size: 20px;
  font-weight: 700;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dept-label {
  font-size: 14px;
  color: #666;
}

.refresh-btn {
  padding: 6px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 13px;
}

.refresh-btn:hover {
  background: #f5f5f5;
}

.add-btn {
  padding: 6px 14px;
  border: none;
  border-radius: 6px;
  background: #2196f3;
  color: white;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
}

.add-btn:hover { background: #1976d2; }

.kanban-board {
  padding: 20px 24px;
}

.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(600px, 1fr));
  gap: 16px;
}

.loading, .empty {
  text-align: center;
  padding: 60px 20px;
  color: #999;
  font-size: 15px;
}

.empty code {
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}
</style>
