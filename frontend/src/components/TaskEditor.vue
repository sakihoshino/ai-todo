<script setup>
import { onMounted, reactive, ref } from 'vue'
import { X } from '@lucide/vue'
import { categories, priorities, editableFields } from '../tasks.js'

const props = defineProps({ task: Object, busy: Boolean, creating: Boolean, error: String })
const emit = defineEmits(['save', 'close'])
const dialog = ref(null)
const form = reactive(editableFields(props.task))
onMounted(() => dialog.value.showModal())

function save() {
  if (!form.title.trim()) return
  emit('save', editableFields(form))
}
</script>
<template>
  <dialog ref="dialog" class="form-dialog" aria-labelledby="edit-heading" @cancel.prevent="!busy && emit('close')">
    <form @submit.prevent="save">
      <div class="dialog-heading"><h2 id="edit-heading">{{ creating ? '新增任务' : '编辑任务' }}</h2><button type="button" class="icon-btn" :disabled="busy" aria-label="关闭编辑" @click="emit('close')"><X :size="18"/></button></div>
      <fieldset :disabled="busy" class="edit-grid">
        <label class="col-span-2">任务名称<input v-model="form.title" required maxlength="200" autofocus></label>
        <label class="col-span-2">补充说明<textarea v-model="form.description" rows="3" maxlength="2000" placeholder="可选"></textarea></label>
        <label>任务分类<select v-model="form.category"><option v-for="[name] in categories" :key="name">{{ name }}</option></select></label>
        <label>优先级<select v-model="form.priority"><option v-for="p in priorities" :key="p">{{ p }}</option></select></label>
        <label>截止日期<input type="date" v-model="form.due_date"></label>
        <label>截止时间<input type="time" v-model="form.due_time"></label>
      </fieldset>
      <p v-if="error" class="error-message" role="alert">{{ error }}</p>
      <div class="dialog-actions"><button class="secondary-btn" type="button" :disabled="busy" @click="emit('close')">取消</button><button class="primary-btn" :disabled="busy || !form.title.trim()">{{ busy ? '正在保存…' : creating ? '保存任务' : '保存修改' }}</button></div>
    </form>
  </dialog>
</template>
