import 'fake-indexeddb/auto'
import assert from 'node:assert/strict'
import { test, type TestContext } from 'node:test'
import Dexie from 'dexie'
import type { Task, TaskDraft } from '../src/local/models.ts'
import { TaskRepository } from '../src/local/repository.ts'

const draft: TaskDraft = {
  title: '读论文', description: '', category: '科学研究', due_date: null, due_time: null, priority: '中',
}
function fresh(t: TestContext, name = crypto.randomUUID()) {
  const repo = new TaskRepository(name)
  t.after(() => repo.close())
  return repo
}
const oldTask = (): Task => ({
  ...draft, id: crypto.randomUUID(), raw_input: ' 有空时读论文 ', status: '已完成',
  created_at: '2026-11-01T02:00:00.000001+00:00', updated_at: '2026-11-04T02:00:00.000123+00:00',
  completed_at: '2026-11-04T02:00:00.000123+00:00',
})

test('确认后的增删改、完成与恢复在时间线上可回看', async t => {
  const repo = fresh(t)
  const [saved] = await repo.saveBatch(' 有空时读论文 ', [{...draft, title: '阅读指定论文'}])
  assert.equal(saved.raw_input, ' 有空时读论文 ')
  assert.equal(saved.due_date, null)
  assert.equal(saved.title, '阅读指定论文')
  const done = await repo.updateTask(saved.id, { status: '已完成' })
  assert.ok(done.completed_at)
  assert.deepEqual(await repo.updateTask(saved.id, { status: '已完成' }), done)
  const restored = await repo.updateTask(saved.id, { status: '待完成' })
  assert.equal(restored.completed_at, null)
  const edited = await repo.updateTask(saved.id, { description: '先看引言', due_date: '2026-11-25' })
  assert.equal(edited.id, saved.id)
  assert.equal((await repo.getTask(saved.id))?.description, '先看引言')
  assert.equal((await repo.updateTask(saved.id, {due_date: null})).due_date, null)
  await repo.deleteTask(saved.id)
  assert.equal(await repo.getTask(saved.id), undefined)
  assert.deepEqual((await repo.listHistory(saved.id)).map(entry => entry.action), ['删除', '编辑', '编辑', '恢复', '完成', '创建'])
  await assert.rejects(repo.updateTask(saved.id, {title: '新名称'}))
  await assert.rejects(repo.deleteTask(saved.id))
})

test('同一批次跨标签页并发、关闭再打开和失败重试', async t => {
  const name = crypto.randomUUID()
  const repo = fresh(t, name)
  const otherTab = fresh(t, name)
  const key = crypto.randomUUID()
  const save = (target: TaskRepository) => target.saveBatch('读论文', [draft], key)
  const [first, repeated] = await Promise.all([save(repo), save(otherTab)])
  assert.deepEqual(first, repeated)
  assert.equal((await repo.listHistory()).length, 1)
  await assert.rejects(repo.saveBatch('改个原文', [draft], key), /重新确认/)
  repo.close()
  otherTab.close()
  const restarted = fresh(t, name)
  assert.deepEqual(await restarted.listTasks(), first)
  assert.deepEqual(await save(restarted), first)
  assert.equal((await restarted.listHistory()).length, 1)
})

test('真实事务中历史记录写入失败时，任务、历史与批次凭据一起回滚', async t => {
  const repo = fresh(t)
  const key = crypto.randomUUID()
  const add = IDBObjectStore.prototype.add
  const fault = t.mock.method(IDBObjectStore.prototype, 'add', function(this: IDBObjectStore, ...args: Parameters<typeof add>) {
    if (this.name === 'history') throw new DOMException('测试写满', 'QuotaExceededError')
    return add.apply(this, args)
  })
  await assert.rejects(repo.saveBatch('读论文', [draft], key))
  fault.mock.restore()
  assert.deepEqual(await repo.listTasks(), [])
  assert.deepEqual(await repo.listHistory(), [])
  const [task] = await repo.saveBatch('读论文', [draft], key)
  assert.equal((await repo.listHistory())[0].task_id, task.id)
})

test('拒绝错误日期、无效字段和混入坏任务的整批写入', async t => {
  const repo = fresh(t)
  await assert.rejects(repo.saveBatch('读论文', [draft, {...draft, due_date: '2026-02-30'}]))
  assert.equal((await repo.listTasks()).length, 0)
  const [task] = await repo.saveBatch('读论文', [draft])
  await assert.rejects(repo.updateTask(task.id, { due_time: '33:45' }))
  await assert.rejects(repo.updateTask(task.id, { ...{raw_input: '新原文'}, title: '写作业' }))
  assert.deepEqual(await repo.getTask(task.id), task)
  assert.equal((await repo.listHistory()).length, 1)
})

test('分类和完成状态筛选，截止顺序与即将到期的七天边界', async t => {
  const repo = fresh(t)
  const rows = await repo.saveBatch('学习计划', [
    {...draft, title: '今日', due_date: '2026-11-24', due_time: '10:00'},
    {...draft, title: '一周', due_date: '2026-12-01'},
    {...draft, title: '未来', due_date: '2026-12-02'},
    {...draft, title: '已完成', due_date: '2026-11-25'},
    {...draft, title: '待定', category: '课程学习'},
  ])
  await repo.updateTask(rows[3].id, {status: '已完成'})
  const titles = async (q: Parameters<TaskRepository['listTasks']>[0]) => (await repo.listTasks(q)).map(task => task.title)
  assert.deepEqual(await titles({view: 'today', today: '2026-11-24'}), ['今日'])
  assert.deepEqual(await titles({view: 'upcoming', today: '2026-11-24'}), ['一周'])
  assert.deepEqual(await titles({view: 'completed'}), ['已完成'])
  assert.deepEqual(await titles({category: '课程学习', status: '待完成'}), ['待定'])
  assert.deepEqual(await titles({sort: 'due_asc'}), ['今日', '已完成', '一周', '未来', '待定'])
  assert.deepEqual(await titles({sort: 'due_desc'}), ['未来', '一周', '已完成', '今日', '待定'])
})

test('IndexedDB v1→v2 数据升级保留全部字段并回填导入记录', async t => {
  const name = crypto.randomUUID()
  const legacy = new Dexie(name)
  legacy.version(1).stores({tasks: 'id,category,status,due_date'})
  const task = oldTask()
  await legacy.table('tasks').add(task)
  legacy.close()
  const upgraded = fresh(t, name)
  assert.deepEqual(await upgraded.getTask(task.id), task)
  assert.deepEqual((await upgraded.listHistory()).map(row => [row.task_id, row.action]), [[task.id, '导入']])
  const [newTask] = await upgraded.saveBatch('读论文', [draft])
  assert.notEqual(newTask.id, task.id)
})

test('V0.1 JSON 迁入，整库往返迁移，重复导入保护本机编辑', async t => {
  const source = fresh(t)
  const task = oldTask()
  assert.deepEqual(await source.importBackup({tasks: [task]}), {added: 1, skipped: 0})
  assert.deepEqual(await source.getTask(task.id), task)
  const [deleted] = await source.saveBatch('下单买牛奶', [{...draft, title: '下单买牛奶'}])
  await source.deleteTask(deleted.id)
  const snapshot = await source.exportBackup()
  const target = fresh(t)
  assert.deepEqual(await target.importBackup(JSON.parse(JSON.stringify(snapshot))), {added: 1, skipped: 0})
  assert.deepEqual(await target.exportBackup(), snapshot)
  await target.updateTask(task.id, {title: '本机已修改'})
  assert.deepEqual(await target.importBackup(snapshot), {added: 0, skipped: 1})
  assert.equal((await target.getTask(task.id))?.title, '本机已修改')
  assert.equal((await target.listHistory()).length, snapshot.history.length + 1)
  await assert.rejects(target.importBackup({...snapshot, version: 3}))
  await assert.rejects(target.importBackup({tasks: [task, {...task, id: crypto.randomUUID(), due_date: 'bad'}]}))
  assert.equal((await target.listTasks()).length, 1)
})
