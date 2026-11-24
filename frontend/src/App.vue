<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  ArrowDownUp, ArrowRight, BookOpen, CalendarDays, Check, ChevronDown, ChevronRight,
  CircleAlert, ClipboardList, Feather, FileText, Languages, ListChecks, LoaderCircle,
  Menu, PanelLeft, Pencil, Plus, Settings2, SlidersHorizontal, Sparkles, Trash2, X,
} from '@lucide/vue'
import Navigation from './components/Navigation.vue'
import TaskEditor from './components/TaskEditor.vue'
import HistoryPanel from './components/HistoryPanel.vue'
import ParserSettings from './components/ParserSettings.vue'
import { legacy, listHistory, listTasks, parseInput, publicBase, readState, removeTask, saveBatch, settings, updateTask } from './workspace'
import { createId, selectTasks } from './local/repository'
import { categories, dayOffset, editableFields, examples } from './tasks.js'

const tasks = ref([]), health = ref(null), loading = ref(true), loadError = ref('')
const input = ref(''), inputEl = ref(null), drafts = ref([]), draftRaw = ref('')
const parsing = ref(false), saving = ref(false), composeError = ref(''), composeInfo = ref('')
const previewEl = ref(null), draftKey = ref(''), lastBatch = ref('')
const active = ref('all'), status = ref('全部状态'), sort = ref('due_asc')
const editor = ref(null), editError = ref(''), editing = ref(false)
const deleteTarget = ref(null), deleteDialog = ref(null), deleting = ref(false), deleteError = ref('')
const rowBusy = ref({}), rowError = ref(''), navDialog = ref(null), toast = ref('')
const history = ref([]), historyError = ref(''), historyLoading = ref(false)
const settingsOpen = ref(false), online = ref(navigator.onLine)
const inHistory = computed(() => !legacy && active.value === 'history')
const pageTitle = computed(() => inHistory.value ? '操作历史' : '任务工作台')
const onlineParserUnavailable = computed(() => !legacy && settings.mode === 'deepseek' && !online.value)
let toastTimer, healthTimer
const today = computed(() => health.value?.today || new Date().toLocaleDateString('sv-SE'))
const todayLabel = computed(() => new Intl.DateTimeFormat('zh-CN', {year:'numeric',month:'long',day:'numeric',weekday:'long',timeZone:'UTC'}).format(new Date(today.value + 'T12:00:00Z')).replace('星期', ' · 星期'))
const modeLabel = computed(() => {
  if (!legacy) return !online.value ? '离线模式' : settings.mode === 'mock' ? '本地解析' : 'DeepSeek 模式'
  if (!health.value) return '连接本地服务中'
  return health.value.mode === 'mock' ? 'Mock 模式' : health.value.configured ? 'DeepSeek 模式' : '待配置 API Key'
})
const disabledKey = computed(() => health.value?.mode === 'deepseek' && !health.value.configured)
const titles = {all:'全部任务',today:'今日任务',upcoming:'即将到期',completed:'已完成'}
const viewTitle = computed(() => titles[active.value] || active.value)
const lockedStatus = computed(() => ['today','completed','upcoming'].includes(active.value))
const counts = computed(() => ({
  all: tasks.value.length,
  today: tasks.value.filter(t => t.status === '待完成' && t.due_date === today.value).length,
  completed: tasks.value.filter(t => t.status === '已完成').length,
  upcoming: tasks.value.filter(isUpcoming).length,
}))
const sampleIcons = [BookOpen, Languages, FileText]
function isUpcoming(task) {
  const n = dayOffset(task.due_date, today.value)
  return task.status === '待完成' && n >= 1 && n <= 7
}
const visibleTasks = computed(() => selectTasks(tasks.value, {
  view: active.value in titles ? active.value : 'all',
  category: categories.find(([name]) => name === active.value)?.[0],
  status: status.value === '全部状态' ? undefined : status.value,
  sort: sort.value,
  today: today.value,
}))
const hasPreview = computed(() => drafts.value.length > 0)
const busyCompose = computed(() => parsing.value || saving.value)
function navigate(key) {
  active.value = key
  status.value = '全部状态'
  rowError.value = ''
  navDialog.value?.close()
  if (inHistory.value) refreshHistory()
}
async function initialize() {
  loading.value = true
  loadError.value = ''
  try {
    const [state, list] = await Promise.all([readState(), listTasks()])
    health.value = state
    tasks.value = list
  } catch (e) { loadError.value = e.message }
  finally { loading.value = false }
}
async function refreshDate() {
  if (document.visibilityState === 'visible') {
    try { health.value = await readState() } catch { /* User actions report connection failures. */ }
  }
}
async function refreshHistory() {
  historyError.value = ''
  historyLoading.value = true
  try { history.value = await listHistory() }
  catch (e) { historyError.value = e.message }
  finally { historyLoading.value = false }
}
async function resumeWorkspace() {
  if (document.visibilityState !== 'visible') return
  await refreshDate()
  if (!legacy) {
    try {
      tasks.value = await listTasks()
      loadError.value = ''
    } catch(e) { loadError.value = e.message }
    if (inHistory.value) await refreshHistory()
  }
}
// On iOS the keyboard can resize and pan the visual viewport without changing 100dvh.
function updateDialogViewport() {
  const viewport = window.visualViewport
  if (!viewport) return
  const style = document.documentElement.style
  style.setProperty('--visible-height', viewport.height + 'px')
  style.setProperty('--visible-top', viewport.offsetTop + 'px')
}
function setConnectivity() { online.value = navigator.onLine }
async function applySettings(value) {
  Object.assign(settings, value)
  settingsOpen.value = false
  composeError.value = ''
  await refreshDate()
}
onMounted(() => {
  initialize()
  updateDialogViewport()
  window.visualViewport?.addEventListener('resize', updateDialogViewport)
  window.visualViewport?.addEventListener('scroll', updateDialogViewport)
  healthTimer = setInterval(refreshDate, 60000)
  document.addEventListener('visibilitychange', resumeWorkspace)
  if (!legacy) {
    window.addEventListener('focus', resumeWorkspace)
    window.addEventListener('online', setConnectivity)
    window.addEventListener('offline', setConnectivity)
  }
})
onBeforeUnmount(() => {
  clearTimeout(toastTimer)
  clearInterval(healthTimer)
  window.visualViewport?.removeEventListener('resize', updateDialogViewport)
  window.visualViewport?.removeEventListener('scroll', updateDialogViewport)
  document.removeEventListener('visibilitychange', resumeWorkspace)
  window.removeEventListener('focus', resumeWorkspace)
  window.removeEventListener('online', setConnectivity)
  window.removeEventListener('offline', setConnectivity)
})
function inform(message) {
  toast.value = message
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 3200)
}
function useExample(text) {
  if (busyCompose.value || hasPreview.value) return
  input.value = text
  composeError.value = composeInfo.value = ''
  inputEl.value?.focus()
}
async function parse() {
  if (!input.value.trim() || hasPreview.value || busyCompose.value || disabledKey.value || onlineParserUnavailable.value || !health.value) return
  composeError.value = composeInfo.value = ''
  parsing.value = true
  const raw = input.value
  try {
    drafts.value = (await parseInput(raw)).map(editableFields)
    draftRaw.value = raw
    if (!hasPreview.value) composeInfo.value = '没有识别到可执行的任务，可以换个说法再试。'
    else {
      await nextTick()
      previewEl.value?.focus()
    }
  } catch(e) { composeError.value = e.message }
  finally { parsing.value = false }
}
function discard() {
  drafts.value = []
  draftKey.value = lastBatch.value = composeError.value = composeInfo.value = ''
  nextTick(() => inputEl.value?.focus())
}
async function saveDrafts() {
  if (!hasPreview.value || saving.value || drafts.value.some(t => !t.title.trim())) return
  saving.value = true
  composeError.value = ''
  const body = JSON.stringify({raw_input:draftRaw.value, tasks:drafts.value.map(editableFields)})
  if (lastBatch.value !== body) {
    draftKey.value = createId()
    lastBatch.value = body
  }
  try {
    const saved = await saveBatch(draftRaw.value, drafts.value.map(editableFields), draftKey.value)
    tasks.value = [...saved, ...tasks.value.filter(t => !saved.some(s => s.id === t.id))]
    navigate('all')
    drafts.value = []
    input.value = draftRaw.value = draftKey.value = lastBatch.value = ''
    inform('已保存 ' + saved.length + ' 项任务')
  } catch(e) { composeError.value = e.message }
  finally { saving.value = false }
}
function openEditor(task, index = null) {
  editError.value = ''
  editor.value = {task, index}
}
function newTask() {
  editError.value = ''
  editor.value = {creating: true, key: createId(), index: null, task: {
    title: '', description: '', category: categories.some(([name]) => name === active.value) ? active.value : '其他',
    due_date: active.value === 'today' ? today.value : null, due_time: null, priority: '中',
  }}
}
function replaceTask(task) {
  tasks.value = tasks.value.map(t => t.id === task.id ? task : t)
}
async function saveEdit(fields) {
  if (editing.value) return
  editError.value = ''
  if (editor.value.index !== null) {
    drafts.value[editor.value.index] = fields
    editor.value = null
    return
  }
  editing.value = true
  try {
    if (editor.value.creating) {
      const saved = await saveBatch(fields.title, [fields], editor.value.key)
      tasks.value = [...saved, ...tasks.value]
      navigate('all')
      inform('任务已创建')
    } else {
      replaceTask(await updateTask(editor.value.task.id, fields))
      inform('任务已更新')
    }
    editor.value = null
  } catch(e) { editError.value = e.message }
  finally { editing.value = false }
}
async function toggle(task) {
  if (rowBusy.value[task.id]) return
  rowBusy.value[task.id] = true
  rowError.value = ''
  try {
    replaceTask(await updateTask(task.id, {status:task.status === '待完成' ? '已完成' : '待完成'}))
  } catch(e) { rowError.value = e.message }
  finally { delete rowBusy.value[task.id] }
}
function askDelete(task) {
  deleteTarget.value = task
  deleteError.value = ''
  deleteDialog.value.showModal()
}
async function confirmDelete() {
  if (deleting.value || !deleteTarget.value) return
  deleting.value = true
  try {
    await removeTask(deleteTarget.value.id)
    tasks.value = tasks.value.filter(t => t.id !== deleteTarget.value.id)
    deleteDialog.value.close()
    inform('任务已删除')
  } catch(e) { deleteError.value = e.message }
  finally { deleting.value = false }
}
function deadline(task) {
  const offset = dayOffset(task.due_date, today.value)
  const date = offset === 0 ? '今天' : offset === 1 ? '明天' : task.due_date || ''
  return [date, task.due_time?.slice(0,5)].filter(Boolean).join(' ') || '无截止日期'
}
const categoryColor = name => categories.find(([key]) => key === name)?.[1]
</script>
<template>
  <div class="workspace">
    <aside class="desktop-sidebar"><Navigation :active="active" :counts="counts" @select="navigate"/></aside>
    <dialog ref="navDialog" class="drawer" aria-label="导航菜单" @click.self="navDialog.close()">
      <Navigation mobile :active="active" :counts="counts" @select="navigate" @close="navDialog.close()"/>
    </dialog>
    <div class="main-area">
      <header class="topbar">
        <div class="breadcrumbs flex items-center">
          <button class="icon-btn mobile-nav-btn" aria-label="打开导航" @click="navDialog.showModal()"><Menu :size="20"/></button>
          <PanelLeft class="desktop-crumb" :size="16"/><span>个人空间</span><ChevronRight :size="12"/><strong>{{ pageTitle }}</strong>
        </div>
        <div class="header-tools">
          <span class="mode-indicator" :class="{ offline: disabledKey || loadError || (!legacy && !online) }"><i></i>{{ loadError && !health ? (legacy ? '服务未连接' : '本地存储异常') : modeLabel }}</span>
          <button v-if="!legacy" class="icon-btn" aria-label="解析设置" title="解析设置" :disabled="busyCompose" @click="settingsOpen = true"><Settings2 :size="17"/></button>
        </div>
      </header>
      <main>
        <div class="page-heading">
          <h1>{{ pageTitle }}</h1>
          <span class="date-stamp"><CalendarDays :size="15"/>{{ todayLabel }}</span>
        </div>
        <template v-if="inHistory">
          <p v-if="historyError" role="alert" class="error-message">{{ historyError }} <button class="text-btn" @click="refreshHistory">重试</button></p>
          <HistoryPanel v-else :entries="history" :loading="historyLoading" @imported="resumeWorkspace"/>
        </template>
        <template v-else>
        <section class="composer" aria-labelledby="composer-title">
          <img :src="publicBase + 'desk-note.webp'" alt="" class="notebook-art">
          <div class="composer-content">
            <div class="composer-title"><Feather :size="22" :stroke-width="1.6"/><h2 id="composer-title">AI 快速记录</h2></div>
            <p class="composer-intro">{{ !legacy && settings.mode === 'mock' ? '写下待办，在设备上拆分和分类。' : '写下待办，AI 帮你拆分和分类。' }}</p>
            <div class="capture-box">
              <textarea ref="inputEl" v-model="input" placeholder="今天有什么想做的？直接告诉我就好。" aria-label="任务输入" maxlength="4000" :readonly="busyCompose || hasPreview"
                @input="composeError = composeInfo = ''" @keydown.meta.enter.prevent="parse" @keydown.ctrl.enter.prevent="parse"></textarea>
              <div class="capture-actions">
                <button type="button" class="sample-link" :disabled="busyCompose || hasPreview" @click="useExample('明天写完数据库作业，周五之前提交社区实践周记，今天晚上背50个六级单词，还有空的时候看一下学长发来的论文。')">试试示例<ArrowRight :size="13"/></button>
                <button class="primary-btn parse-btn" :aria-busy="parsing" :disabled="busyCompose || hasPreview || disabledKey || onlineParserUnavailable || !health || !input.trim()" @click="parse">
                  <LoaderCircle v-if="parsing" class="spin" :size="15"/><Sparkles v-else :size="15"/>{{ parsing ? '正在整理…' : 'AI 整理任务' }}
                </button>
              </div>
            </div>
          </div>
        </section>
        <p v-if="legacy && (disabledKey || (health?.mode === 'mock' && !health.configured))" class="mode-note"><CircleAlert :size="14"/><span>{{ disabledKey ? '请在 backend/.env 填写 DEEPSEEK_API_KEY 并重启服务，或切换到 Mock 模式。' : '当前使用本地 Mock 解析。配置 DeepSeek API Key 后可切换为 AI 解析。' }}</span></p>
        <p v-if="onlineParserUnavailable" class="mode-note"><CircleAlert :size="14"/>设备已离线。可手动新增任务，或在解析设置中切换至本地规则。</p>
        <p v-if="composeInfo" class="info-message" role="status">{{ composeInfo }}</p>
        <p v-if="composeError && !hasPreview" class="error-message" role="alert">{{ composeError }}</p>

        <section v-if="hasPreview" ref="previewEl" tabindex="-1" class="preview-panel" aria-labelledby="preview-title">
          <div class="preview-heading"><h2 id="preview-title">待确认任务 <small>{{ drafts.length }}</small></h2><button class="text-btn" :disabled="saving" @click="discard">取消预览</button></div>
          <p class="preview-help">确认名称与时间后，统一保存到清单。</p>
          <div v-for="(t,index) in drafts" :key="index" class="preview-row">
            <div class="grow min-w-0">
              <input v-model="t.title" class="draft-title" aria-label="预览任务名称" maxlength="200" :disabled="saving">
              <div class="task-tags"><span class="category-chip"><i :style="{ background:categoryColor(t.category) }"></i>{{ t.category }}</span><span>{{ deadline(t) }}</span><span>{{ t.priority }}优先级</span></div>
            </div>
            <button class="icon-btn" aria-label="编辑预览任务" :disabled="saving" title="编辑预览任务" @click="openEditor(t,index)"><Pencil :size="15"/></button>
            <button class="icon-btn" aria-label="移除预览任务" :disabled="saving" title="移除预览任务" @click="drafts.splice(index,1); if (!drafts.length) discard()"><X :size="16"/></button>
          </div>
          <p v-if="composeError" class="error-message" role="alert">{{ composeError }}</p>
          <div class="preview-footer"><button class="primary-btn" :disabled="saving || drafts.some(t => !t.title.trim())" @click="saveDrafts"><Check :size="16"/>{{ saving ? '正在保存…' : '确认保存' }}</button></div>
        </section>

        <section class="task-section" aria-labelledby="list-title">
          <div class="list-heading">
            <div class="list-title"><h2 id="list-title">{{ viewTitle }}</h2><span class="list-count">{{ visibleTasks.length }}</span></div>
            <div class="list-controls">
              <button v-if="!legacy" class="manual-add" :disabled="loading || !!loadError" @click="newTask"><Plus :size="14"/>新增任务</button>
              <label v-if="!lockedStatus" class="select-control"><SlidersHorizontal :size="14"/><select v-model="status" aria-label="按完成状态筛选"><option>全部状态</option><option>待完成</option><option>已完成</option></select><ChevronDown :size="12"/></label>
              <label class="select-control"><ArrowDownUp :size="14"/><select v-model="sort" aria-label="排序方式"><option value="due_asc">截止日期升序</option><option value="due_desc">截止日期降序</option><option value="created_desc">最近创建</option></select><ChevronDown :size="12"/></label>
            </div>
          </div>
          <p v-if="active === 'upcoming'" class="view-hint">明天起 7 天内到期的待办</p>
          <p v-if="rowError" class="error-message" role="alert">{{ rowError }}</p>
          <div v-if="loading" class="simple-empty" role="status"><LoaderCircle class="spin" :size="20"/>正在读取任务…</div>
          <div v-else-if="loadError" class="simple-empty" role="alert"><CircleAlert :size="22"/>{{ loadError }}<button class="secondary-btn" @click="initialize">重新连接</button></div>
          <template v-else-if="visibleTasks.length">
            <ul class="task-list">
              <li v-for="task in visibleTasks" :key="task.id" data-testid="task-row" class="task-row" :class="{ done: task.status === '已完成' }">
                <button class="task-check" role="checkbox" :aria-checked="task.status === '已完成'" :aria-label="task.status === '已完成' ? '恢复待办' : '标记完成'" :disabled="rowBusy[task.id]" @click="toggle(task)"><Check v-if="task.status === '已完成'" :size="13"/></button>
                <div class="task-body">
                  <strong>{{ task.title }}</strong><p v-if="task.description" class="task-description">{{ task.description }}</p>
                  <div class="task-tags"><span class="category-chip"><i :style="{ background:categoryColor(task.category) }"></i>{{ task.category }}</span><span :class="{overdue:task.status === '待完成' && task.due_date && task.due_date < today}"><CalendarDays :size="12"/>{{ deadline(task) }}</span><span :class="{'priority-high':task.priority === '高'}">{{ task.priority }}优先级</span></div>
                </div>
                <div class="row-actions"><button aria-label="编辑任务" title="编辑任务" class="icon-btn" :disabled="rowBusy[task.id]" @click="openEditor(task)"><Pencil :size="15"/></button><button class="icon-btn" aria-label="删除任务" title="删除任务" :disabled="rowBusy[task.id]" @click="askDelete(task)"><Trash2 :size="15"/></button></div>
              </li>
            </ul>
          </template>
          <div v-else-if="!tasks.length && active === 'all' && status === '全部状态'" class="first-use">
            <div class="empty-title"><span class="empty-icon"><ClipboardList :size="22" :stroke-width="1.5"/></span><h3>清单还是空的</h3></div>
            <p>试试下面的示例，记下你的第一项任务。</p>
            <div class="example-grid">
              <button v-for="(sample,i) in examples" :key="sample.text" class="example-card" :disabled="busyCompose || hasPreview" @click="useExample(sample.text)">
                <span class="example-caption"><span class="example-icon" :class="'tint-'+i"><component :is="sampleIcons[i]" :size="16"/></span>{{ sample.category }}<ArrowRight :size="14" class="example-arrow"/></span>
                <span class="example-text">{{ sample.text }}</span>
              </button>
            </div>
          </div>
          <div v-else class="simple-empty"><ListChecks :size="29" :stroke-width="1.5"/><strong>暂无符合条件的任务</strong><button class="text-btn" @click="navigate('all')">查看全部任务 <ArrowRight :size="13"/></button></div>
        </section>
        </template>
      </main>
    </div>
    <ParserSettings v-if="settingsOpen && !legacy" @save="applySettings" @close="settingsOpen = false"/>
    <TaskEditor v-if="editor" :creating="editor.creating" :task="editor.task" :busy="editing" :error="editError" @save="saveEdit" @close="editor = null"/>
    <dialog ref="deleteDialog" class="form-dialog delete-dialog" aria-labelledby="delete-heading" @cancel="deleting && $event.preventDefault()">
      <h2 id="delete-heading">删除这项任务？</h2><p class="delete-detail">「{{ deleteTarget?.title }}」将从清单中永久移除。</p>
      <p v-if="deleteError" class="error-message" role="alert">{{ deleteError }}</p>
      <div class="dialog-actions"><button class="secondary-btn" autofocus :disabled="deleting" @click="deleteDialog.close()">取消</button><button class="danger-btn" :disabled="deleting" @click="confirmDelete">确认删除</button></div>
    </dialog>
    <Transition name="notice"><div v-if="toast" class="toast" role="status"><Check :size="16"/>{{ toast }}</div></Transition>
  </div>
</template>
