<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  submit: [data: { name: string; pinyin: string; role: string; salary: string }]
  cancel: []
}>()

const name = ref('')
const pinyin = ref('')
const role = ref('')
const salary = ref('面议')

const errors = ref<Record<string, string>>({})

function validate(): boolean {
  errors.value = {}
  if (!name.value.trim()) errors.value.name = '请输入姓名'
  if (!pinyin.value.trim()) errors.value.pinyin = '请输入拼音'
  else if (!/^[a-z]+$/.test(pinyin.value)) errors.value.pinyin = '拼音只能用小写字母'
  if (!role.value.trim()) errors.value.role = '请输入岗位'
  return Object.keys(errors.value).length === 0
}

function handleSubmit() {
  if (!validate()) return
  emit('submit', {
    name: name.value.trim(),
    pinyin: pinyin.value.trim(),
    role: role.value.trim(),
    salary: salary.value.trim() || '面议',
  })
}
</script>

<template>
  <div class="dialog-overlay" @click.self="emit('cancel')">
    <div class="dialog">
      <h2 class="dialog-title">➕ 新建候选人</h2>

      <div class="form-field">
        <label>姓名 <span class="required">*</span></label>
        <input v-model="name" placeholder="如：张磊" />
        <span v-if="errors.name" class="error">{{ errors.name }}</span>
      </div>

      <div class="form-field">
        <label>拼音标识 <span class="required">*</span></label>
        <input v-model="pinyin" placeholder="如：zhanglei（小写字母）" />
        <span v-if="errors.pinyin" class="error">{{ errors.pinyin }}</span>
      </div>

      <div class="form-field">
        <label>岗位 <span class="required">*</span></label>
        <input v-model="role" placeholder="如：后端工程师" />
        <span v-if="errors.role" class="error">{{ errors.role }}</span>
      </div>

      <div class="form-field">
        <label>薪资</label>
        <input v-model="salary" placeholder="如：32K（默认面议）" />
      </div>

      <div class="dialog-actions">
        <button class="btn btn-cancel" @click="emit('cancel')">取消</button>
        <button class="btn btn-submit" @click="handleSubmit">创建</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  background: white;
  border-radius: 12px;
  padding: 24px;
  width: 380px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.2);
}

.dialog-title {
  margin: 0 0 20px;
  font-size: 18px;
}

.form-field {
  margin-bottom: 14px;
}

.form-field label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 4px;
  color: #333;
}

.required { color: #f44336; }

.form-field input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
  box-sizing: border-box;
}

.form-field input:focus { border-color: #2196f3; }

.error { font-size: 11px; color: #f44336; margin-top: 2px; display: block; }

.dialog-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 20px;
}

.btn {
  padding: 8px 18px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
}

.btn-cancel { background: #f5f5f5; color: #666; }
.btn-submit { background: #2196f3; color: white; }
.btn-submit:hover { background: #1976d2; }
</style>
