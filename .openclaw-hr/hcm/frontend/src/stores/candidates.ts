import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import type { Candidate, Department, DepartmentConfig, PrepNode } from '../types'
import { DEPARTMENTS } from '../types'

export const useCandidatesStore = defineStore('candidates', () => {
  const candidates = ref<Candidate[]>([])
  const loading = ref(false)
  const currentDepartment = ref<Department>('overview')
  const selectedCandidateId = ref<number | null>(null)

  const currentDeptConfig = computed<DepartmentConfig>(() =>
    DEPARTMENTS.find(d => d.key === currentDepartment.value) ?? DEPARTMENTS[5]
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
      const { data } = await axios.put<PrepNode>(`/api/candidates/${candidateId}/prep/${nodeType}`, body)
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

  async function updateReview(candidateId: number, reviewType: string, status: string, content?: string) {
    try {
      const body: Record<string, any> = { status }
      if (content !== undefined) body.content = content
      const { data } = await axios.put(`/api/candidates/${candidateId}/reviews/${reviewType}`, body)
      const c = candidates.value.find(c => c.id === candidateId)
      if (c) {
        const review = c.reviews.find(r => r.review_type === reviewType)
        if (review) {
          review.status = data.status
          review.content = data.content
          review.completed_at = data.completed_at
        }
      }
    } catch (e) {
      console.error('Failed to update review:', e)
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
    } else if (event.event === 'review_updated') {
      const c = candidates.value.find(c => c.id === event.data.candidate_id)
      if (c) {
        const review = c.reviews.find(r => r.review_type === event.data.review_type)
        if (review) {
          review.status = event.data.status
          review.content = event.data.content
        }
      }
    }
  }

  function setDepartment(dept: Department) {
    currentDepartment.value = dept
  }

  function selectCandidate(id: number | null) {
    selectedCandidateId.value = id
  }

  return {
    candidates,
    loading,
    currentDepartment,
    currentDeptConfig,
    selectedCandidateId,
    selectedCandidate,
    fetchCandidates,
    updatePrepNode,
    createCandidate,
    updateCandidate,
    updateReview,
    handleWSEvent,
    setDepartment,
    selectCandidate,
  }
})
