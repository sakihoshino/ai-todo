import { reactive } from 'vue'
import systemPrompt from 'virtual:task-system-prompt'
import type { Task, TaskDraft, HistoryEntry } from './local/models'
import { parseTasks } from './local/parser'
import { repository } from './local/repository'
import { api } from './tasks.js'

export const legacy = import.meta.env.MODE === 'legacy'
export const publicBase = import.meta.env.BASE_URL
const timeZone = 'Asia/Shanghai'
export interface ParserSettings {
  mode: 'mock' | 'deepseek'
  model: string
  apiKey: string
}

// Credentials live only in this tab's memory. No storage adapter receives these settings.
export const settings = reactive<ParserSettings>({ mode: 'mock', model: 'deepseek-flash', apiKey: '' })
export async function readState() {
  return legacy ? await api('health') : {
    mode: settings.mode,
    configured: Boolean(settings.apiKey),
    today: new Date().toLocaleDateString('sv-SE', {timeZone}),
    timezone: timeZone,
  }
}
export async function listTasks(): Promise<Task[]> {
  return legacy ? (await api('tasks')).tasks : repository.listTasks()
}
export async function parseInput(raw: string): Promise<TaskDraft[]> {
  if (legacy) return (await api('tasks/parse', {
    method: 'POST', body: JSON.stringify({ raw_input: raw }),
  })).tasks
  return parseTasks(raw, { ...settings, timeZone, systemPrompt })
}
export async function saveBatch(raw: string, drafts: TaskDraft[], key: string): Promise<Task[]> {
  if (legacy) return (await api('tasks/batch', {
    method: 'POST', headers: {'Idempotency-Key': key},
    body: JSON.stringify({ raw_input: raw, tasks: drafts }),
  })).tasks
  return repository.saveBatch(raw, drafts, key)
}
export async function updateTask(id: string, patch: Partial<TaskDraft> & {status?: Task['status']}): Promise<Task> {
  if (legacy) return api('tasks/' + id, {method:'PATCH', body: JSON.stringify(patch)})
  return repository.updateTask(id, patch)
}
export async function removeTask(id: string): Promise<void> {
  if (legacy) await api('tasks/' + id, {method:'DELETE'})
  else await repository.deleteTask(id)
}
export async function listHistory(): Promise<HistoryEntry[]> { return repository.listHistory() }
