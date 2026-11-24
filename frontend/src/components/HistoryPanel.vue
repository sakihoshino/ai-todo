<script setup lang="ts">
import { ref } from 'vue'
import { ArrowDownToLine, FileUp, History } from '@lucide/vue'
import type { HistoryEntry } from '../local/models'
import { repository } from '../local/repository'

defineProps<{entries: HistoryEntry[]; loading: boolean}>()
const emit = defineEmits<{ imported: [] }>()
const picker = ref<HTMLInputElement | null>(null)
const busy = ref(false)
const message = ref('')
const error = ref('')
const formatter = new Intl.DateTimeFormat('zh-CN', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Shanghai',
})

async function importFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  busy.value = true
  message.value = error.value = ''
  try {
    let content: unknown
    try { content = JSON.parse(await file.text()) } catch { throw new Error('无法读取 JSON 文件，请选择导出的任务备份。') }
    const result = await repository.importBackup(content)
    message.value = '已导入 ' + result.added + ' 项任务，跳过 ' + result.skipped + ' 项已有任务。'
    emit('imported')
  } catch (e) { error.value = e instanceof Error ? e.message : '导入失败。' }
  finally { input.value = ''; busy.value = false }
}
async function exportFile() {
  busy.value = true
  message.value = error.value = ''
  try {
    const data = await repository.exportBackup()
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'AI-Todo-' + new Date().toLocaleDateString('sv-SE') + '.json'
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 60000)
    message.value = '备份已生成。'
  } catch(e) { error.value = e instanceof Error ? e.message : '导出失败。' }
  finally { busy.value = false }
}
</script>
<template>
  <section class="history-panel" aria-label="操作记录">
    <div class="list-heading">
      <div class="list-title"><h2>变更记录</h2><span class="list-count">{{ entries.length }}</span></div>
      <div class="list-controls">
        <button class="secondary-btn" :disabled="busy" @click="picker?.click()"><FileUp :size="14"/>导入任务</button>
        <button class="secondary-btn" :disabled="busy" @click="exportFile"><ArrowDownToLine :size="14"/>导出备份</button>
      </div>
    </div>
    <input type="file" ref="picker" accept=".json,application/json" class="hidden" aria-label="选择任务备份" @change="importFile">
    <p class="settings-caption">可导入旧版导出的任务 JSON 或本地备份，已有的任务会自动跳过。</p>
    <p v-if="message" class="info-message" role="status">{{ message }}</p>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    <ul v-if="entries.length">
      <li v-for="entry in entries" :key="entry.id" class="history-row">
        <span class="history-action">{{ entry.action }}</span>
        <div><strong>{{ entry.title }}</strong><time :datetime="entry.timestamp">{{ formatter.format(new Date(entry.timestamp)) }}</time></div>
      </li>
    </ul>
    <div v-else-if="loading" class="simple-empty" role="status">正在读取操作历史…</div>
    <div v-else class="simple-empty"><History :size="26" :stroke-width="1.5"/><strong>还没有操作记录</strong><span>新建、修改或删除任务后，可在这里回看。</span></div>
  </section>
</template>
