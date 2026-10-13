/** TypeScript type definitions for HCM system. */

export interface PrepNode {
  id: number
  candidate_id: number
  node_type: 'contract' | 'account' | 'device' | 'training' | 'buddy'
  status: 'pending' | 'in_progress' | 'completed' | 'paused' | 'rejected'
  data: Record<string, any>
  updated_at: string
}

export interface Candidate {
  id: number
  name: string
  pinyin: string
  role: string
  salary: string
  status: string
  started_at: string | null
  created_at: string
  nodes: PrepNode[]
}

export type AppSection = 'onboarding' | 'monthly'

export type Department = 'hr' | 'it' | 'admin' | 'training' | 'buddy'

export interface DepartmentConfig {
  key: Department
  label: string
  icon: string
  nodeType: PrepNode['node_type']
}

export const DEPARTMENTS: DepartmentConfig[] = [
  { key: 'hr',       label: 'HR',     icon: '👤', nodeType: 'contract' },
  { key: 'it',       label: 'IT',     icon: '💻', nodeType: 'account' },
  { key: 'admin',    label: '行政',   icon: '🏢', nodeType: 'device' },
  { key: 'training', label: '培训部', icon: '📚', nodeType: 'training' },
  { key: 'buddy',    label: '用人部门', icon: '🤝', nodeType: 'buddy' },
]

export const NODE_LABELS: Record<string, string> = {
  contract: '合同签署',
  account: 'IT账号',
  device: '行政设备',
  training: '入职培训',
  buddy: 'Buddy匹配',
}

export const STATUS_COLORS: Record<string, string> = {
  pending: '#9e9e9e',
  in_progress: '#2196f3',
  completed: '#4caf50',
  paused: '#ff9800',
  rejected: '#f44336',
}

export const STATUS_LABELS: Record<string, string> = {
  pending: '未开始',
  in_progress: '进行中',
  completed: '已完成',
  paused: '暂停',
  rejected: '否决',
}
