import Dexie, { type Table } from 'dexie'
import { z } from 'zod'
import {
  backupSchema, draftSchema, legacyBackupSchema, patchSchema, rawInputSchema, taskSchema,
  type Backup, type HistoryEntry, type Task, type TaskDraft, type TaskPatch, type TaskQuery,
} from './models.ts'

const taskStoreV1 = 'id,category,status,due_date'
const draftsSchema = z.array(draftSchema).min(1).max(50)
type StoredHistory = HistoryEntry & { sequence?: number }
type Receipt = { key: string, signature: string, taskIds: string[] }

// randomUUID is restricted to secure contexts. getRandomValues also works on a LAN development origin.
export function createId(): string {
  if (crypto.randomUUID) return crypto.randomUUID()
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6]! & 15) | 64
  bytes[8] = (bytes[8]! & 63) | 128
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join('-')
}

function event(task: Task, action: HistoryEntry['action'], timestamp: string): HistoryEntry {
  return { id: createId(), task_id: task.id, title: task.title, action, timestamp }
}

class LocalDatabase extends Dexie {
  tasks!: Table<Task, string>
  history!: Table<StoredHistory, number>
  batches!: Table<Receipt, string>

  constructor(name: string) {
    super(name)
    this.version(1).stores({ tasks: taskStoreV1 })
    this.version(2).stores({
      tasks: taskStoreV1 + ',created_at',
      history: '++sequence,&id,task_id,timestamp',
      batches: 'key',
    }).upgrade(async tx => {
      // The v1 IndexedDB layout contains complete task rows, but has no event log.
      const existing: Task[] = await tx.table('tasks').toArray()
      const stamp = new Date().toISOString()
      await tx.table('history').bulkAdd(existing.map(row => event(taskSchema.parse(row), '导入', stamp)))
    })
  }
}

function nullableCompare(a: string | null, b: string | null, direction: number): number {
  if (a === b) return 0
  if (a === null) return 1
  if (b === null) return -1
  return direction * a.localeCompare(b)
}

export function selectTasks(tasks: Task[], query: TaskQuery = {}): Task[] {
  const today = query.today ?? new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(new Date())
  const lastDay = new Date(Date.parse(today + 'T00:00:00Z') + 7 * 86400000).toISOString().slice(0, 10)
  const selected = tasks.filter(task => {
    if (query.category && task.category !== query.category) return false
    if (query.status && task.status !== query.status) return false
    if (query.view === 'completed') return task.status === '已完成'
    if (query.view === 'today') return task.status === '待完成' && task.due_date === today
    if (query.view === 'upcoming') {
      return task.status === '待完成' && task.due_date !== null && task.due_date > today && task.due_date <= lastDay
    }
    return true
  })
  return selected.sort((a, b) => {
    if (query.sort !== 'created_desc') {
      const direction = query.sort === 'due_desc' ? -1 : 1
      const due = nullableCompare(a.due_date, b.due_date, direction) || nullableCompare(a.due_time, b.due_time, direction)
      if (due) return due
    }
    return Date.parse(b.created_at) - Date.parse(a.created_at) || a.id.localeCompare(b.id)
  })
}

function plainHistory(row: StoredHistory): HistoryEntry {
  const { sequence: _sequence, ...record } = row
  return record
}

async function signatureOf(rawInput: string, drafts: TaskDraft[]): Promise<string> {
  const text = JSON.stringify([rawInput, drafts])
  if (!crypto.subtle) return text  // local HTTP development only
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')
}

export class TaskRepository {
  private db: LocalDatabase

  constructor(name = 'AI-Todo') {
    this.db = new LocalDatabase(name)
  }

  close() {
    this.db.close()
  }

  async listTasks(query: TaskQuery = {}): Promise<Task[]> {
    return selectTasks(await this.db.tasks.toArray(), query)
  }

  getTask(id: string): Promise<Task | undefined> {
    return this.db.tasks.get(id)
  }

  async listHistory(taskId?: string): Promise<HistoryEntry[]> {
    const rows = taskId ? await this.db.history.where('task_id').equals(taskId).toArray() : await this.db.history.toArray()
    return rows.sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp) || (b.sequence! - a.sequence!))
      .map(plainHistory)
  }

  async saveBatch(rawInput: string, input: TaskDraft[], idempotencyKey?: string): Promise<Task[]> {
    const drafts = draftsSchema.safeParse(input)
    if (!rawInputSchema.safeParse(rawInput).success || !drafts.success) throw new Error('请检查原始输入及待确认任务的内容。')
    // Web Crypto runs before opening the IndexedDB transaction to keep it active.
    const signature = idempotencyKey ? await signatureOf(rawInput, drafts.data) : ''
    return this.db.transaction('rw', this.db.tasks, this.db.history, this.db.batches, async () => {
      if (idempotencyKey) {
        const receipt = await this.db.batches.get(idempotencyKey)
        if (receipt) {
          if (receipt.signature !== signature) throw new Error('这次保存的内容已变更，请重新确认。')
          const rows = await this.db.tasks.bulkGet(receipt.taskIds)
          return rows.filter((task): task is Task => task !== undefined)
        }
      }
      const now = new Date().toISOString()
      const tasks: Task[] = drafts.data.map(draft => ({
        ...draft, id: createId(), raw_input: rawInput, status: '待完成', created_at: now, updated_at: now, completed_at: null,
      }))
      await this.db.tasks.bulkAdd(tasks)
      await this.db.history.bulkAdd(tasks.map(task => event(task, '创建', now)))
      if (idempotencyKey) await this.db.batches.add({ key: idempotencyKey, signature, taskIds: tasks.map(task => task.id) })
      return tasks
    })
  }

  async updateTask(id: string, changes: TaskPatch): Promise<Task> {
    const parsed = patchSchema.safeParse(changes)
    if (!parsed.success) throw new Error('任务修改内容或格式有误。')
    return this.db.transaction('rw', this.db.tasks, this.db.history, async () => {
      const old = await this.db.tasks.get(id)
      if (!old) throw new Error('找不到这项任务。')
      const patch = parsed.data
      const changed = (Object.keys(patch) as (keyof TaskPatch)[]).filter(key => patch[key] !== old[key])
      if (!changed.length) return old
      const now = new Date().toISOString()
      const task = { ...old, ...patch, updated_at: now } as Task
      const events: HistoryEntry[] = []
      if (changed.some(key => key !== 'status')) events.push(event(task, '编辑', now))
      if (old.status !== task.status) {
        task.completed_at = task.status === '已完成' ? now : null
        events.push(event(task, task.status === '已完成' ? '完成' : '恢复', now))
      }
      await this.db.tasks.put(task)
      await this.db.history.bulkAdd(events)
      return task
    })
  }

  async deleteTask(id: string): Promise<void> {
    await this.db.transaction('rw', this.db.tasks, this.db.history, async () => {
      const task = await this.db.tasks.get(id)
      if (!task) throw new Error('找不到这项任务。')
      await this.db.tasks.delete(id)
      await this.db.history.add(event(task, '删除', new Date().toISOString()))
    })
  }

  async exportBackup(): Promise<Backup> {
    return this.db.transaction('r', this.db.tasks, this.db.history, async () => ({
      format: 'AI-Todo' as const, version: 2 as const,
      tasks: await this.db.tasks.toArray(), history: (await this.db.history.toArray()).map(plainHistory),
    }))
  }

  async importBackup(input: unknown): Promise<{ added: number, skipped: number }> {
    const parsed = z.union([backupSchema, legacyBackupSchema]).safeParse(input)
    if (!parsed.success) throw new Error('备份格式或版本无效，请选择 AI-Todo 导出的 JSON 文件。')
    const { tasks } = parsed.data
    const history = 'history' in parsed.data ? parsed.data.history : []
    if (new Set(tasks.map(t => t.id)).size !== tasks.length || new Set(history.map(e => e.id)).size !== history.length) {
      throw new Error('备份含有重复标识，未导入。')
    }
    return this.db.transaction('rw', this.db.tasks, this.db.history, async () => {
      const existing = await this.db.tasks.bulkGet(tasks.map(t => t.id))
      const added = tasks.filter((_, index) => !existing[index])
      const knownEventIds = new Set(await this.db.history.orderBy('id').keys())
      const newEvents = history.filter(entry => !knownEventIds.has(entry.id))
      const withHistory = new Set(history.map(entry => entry.task_id))
      const now = new Date().toISOString()
      await this.db.tasks.bulkAdd(added)
      await this.db.history.bulkAdd([
        ...newEvents,
        ...added.filter(task => !withHistory.has(task.id)).map(task => event(task, '导入', now)),
      ])
      return { added: added.length, skipped: tasks.length - added.length }
    })
  }
}

export const repository = new TaskRepository()
