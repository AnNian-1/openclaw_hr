import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import type { Candidate, Department, DepartmentConfig, PrepNode, AppSection } from '../types'
import { DEPARTMENTS } from '../types'

export const useCandidatesStore = defineStore('candidates', () => {
  const candidates = ref<Candidate[]>([])
  const loading = ref(false)
  const currentDepartment = ref<Department>('hr')
  const appSection = ref<AppSection>('onboarding')
  const selectedCandidateId = ref<number | null>(null)

  const currentDeptConfig = computed<DepartmentConfig>(() =>
    DEPARTMENTS.find(d => d.key === currentDepartment.value) ?? DEPARTMENTS[0]
  )

  const selectedCandidate = computed(() =>
    candidates.value.find(c => c.id === selectedCandidateId.value) ?? null
  )

  async function fetchCandidates() {
    loading.value = true
    try {
      const { data } = await axios.get<Candidate[]>('/api/candidates')
      candidates.value = data
    } catch (e) {
      console.error('Failed to fetch candidates:', e)
    } finally {
      loading.value = false
    }
  }

  async function updatePrepNode(candidateId: number, nodeType: string, status: string, nodeData?: Record<string, any>) {
    try {
      const body: Record<string, any> = { status }
      if (nodeData !== undefined) body.data = nodeData
      const { data } = await axios.put<PrepNode>(
        `/api/candidates/${candidateId}/prep/${nodeType}`,
        body,
        { headers: { 'X-Department-Role': currentDepartment.value } },
      )
      // Update local state
      const c = candidates.value.find(c => c.id === candidateId)
      if (c) {
        const idx = c.nodes.findIndex(n => n.node_type === nodeType)
        if (idx >= 0) c.nodes[idx] = data
      }
    } catch (e) {
      console.error('Failed to update node:', e)
    }
  }

  async function createCandidate(payload: { name: string; pinyin: string; role: string; salary: string }) {
    try {
      const { data } = await axios.post<Candidate>('/api/candidates', payload)
      candidates.value.push(data)
      return data
    } catch (e) {
      console.error('Failed to create candidate:', e)
      throw e
    }
  }

  async function updateCandidate(candidateId: number, patch: { name?: string; role?: string; salary?: string; status?: string }) {
    try {
      const { data } = await axios.put(`/api/candidates/${candidateId}`, patch)
      const c = candidates.value.find(c => c.id === candidateId)
      if (c) {
        if (patch.name !== undefined) c.name = patch.name
        if (patch.role !== undefined) c.role = patch.role
        if (patch.salary !== undefined) c.salary = patch.salary
        if (patch.status !== undefined) c.status = patch.status
      }
    } catch (e) {
      console.error('Failed to update candidate:', e)
    }
  }

  function handleWSEvent(event: { event: string; data: any }) {
    if (event.event === 'node_updated') {
      const c = candidates.value.find(c => c.id === event.data.candidate_id)
      if (c) {
        const node = c.nodes.find(n => n.node_type === event.data.node_type)
        if (node) {
          node.status = event.data.status
          node.data = event.data.data
        }
      }
    }
  }

  function setDepartment(dept: Department) {
    currentDepartment.value = dept
    appSection.value = 'onboarding'
  }

  function showMonthlyReport() {
    appSection.value = 'monthly'
  }

  function selectCandidate(id: number | null) {
    selectedCandidateId.value = id
  }

  return {
    candidates,
    loading,
    currentDepartment,
    appSection,
    currentDeptConfig,
    selectedCandidateId,
    selectedCandidate,
    fetchCandidates,
    updatePrepNode,
    createCandidate,
    updateCandidate,
    handleWSEvent,
    setDepartment,
    showMonthlyReport,
    selectCandidate,
  }
})
