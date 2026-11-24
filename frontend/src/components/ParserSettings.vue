<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { X } from '@lucide/vue'
import { settings, type ParserSettings } from '../workspace'

const emit = defineEmits<{ save: [value: ParserSettings]; close: [] }>()
const dialog = ref<HTMLDialogElement | null>(null)
const draft = reactive<ParserSettings>({...settings})
onMounted(() => dialog.value?.showModal())

function apply() {
  const model = draft.model.trim()
  const apiKey = draft.apiKey.trim()
  if (draft.mode === 'deepseek' && (!model || !apiKey)) return
  emit('save', { mode: draft.mode, model: model || 'deepseek-flash', apiKey })
}
</script>
<template>
  <dialog ref="dialog" class="form-dialog" aria-labelledby="settings-heading" @cancel.prevent="emit('close')">
    <form @submit.prevent="apply">
      <div class="dialog-heading"><h2 id="settings-heading">解析设置</h2><button type="button" aria-label="关闭设置" class="icon-btn" @click="emit('close')"><X :size="18"/></button></div>
      <div class="edit-grid">
        <label class="col-span-2">解析方式<select v-model="draft.mode"><option value="mock">本地规则解析（离线可用）</option><option value="deepseek">DeepSeek 在线解析</option></select></label>
        <template v-if="draft.mode === 'deepseek'">
          <label class="col-span-2">DeepSeek API Key<input v-model="draft.apiKey" type="password" required autocomplete="off" autocapitalize="off" spellcheck="false"></label>
          <label class="col-span-2">模型名称<input v-model="draft.model" required autocomplete="off" autocapitalize="off" spellcheck="false"></label>
        </template>
      </div>
      <p class="settings-caption">{{ draft.mode === 'deepseek' ? '整理时，输入内容将直接发送至 DeepSeek。密钥仅在当前页面内存中使用，刷新后需重新填写。' : '使用设备上的中文规则拆分待办，无需联网或填写密钥。' }}</p>
      <div class="dialog-actions"><button type="button" class="secondary-btn" @click="emit('close')">取消</button><button class="primary-btn">应用设置</button></div>
    </form>
  </dialog>
</template>
