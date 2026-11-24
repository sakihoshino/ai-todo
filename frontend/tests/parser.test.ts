import assert from 'node:assert/strict'
import { test } from 'node:test'
import { parseTasks, type ParseOptions } from '../src/local/parser.ts'

const now = new Date('2026-11-28T15:45:00Z') // Saturday 23:45 in Shanghai.
const sample = '明天写完数据库作业，周五之前提交社区实践周记，今天晚上背50个六级单词，还有空的时候看一下学长发来的论文。'
const draft = { title: '读论文', description: '', category: '科学研究', priority: '中', due_date: null, due_time: null }
const live: ParseOptions = { mode: 'deepseek', apiKey: 'sample-token', model: 'example-model', systemPrompt: '提取任务 JSON', now }

function completion(content: string, reason = 'stop') {
  return Response.json({ choices: [{ finish_reason: reason, message: { content } }] })
}

test('离线拆分示例，保留模糊时间和无日期任务，不访问网络', async () => {
  const tasks = await parseTasks(sample, { now, fetcher: () => assert.fail('本地解析发起了网络请求') })
  assert.deepEqual(tasks.map(t => t.title), ['写完数据库作业', '提交社区实践周记', '背50个六级单词', '看一下学长发来的论文'])
  assert.deepEqual(tasks.map(t => t.category), ['课程学习', '社会实践', '英语学习', '科学研究'])
  assert.deepEqual(tasks.map(t => t.due_date), ['2026-11-29', '2026-12-04', '2026-11-28', null])
  assert.ok(tasks.every(t => t.priority === '中' && t.due_time === null))
})

test('本周、下周、具体时刻、优先级与无日期时刻', async () => {
  const cases = [
    ['本周五读论文', '2026-11-27', null, '中'],
    ['后天写作业', '2026-11-30', null, '中'],
    ['下周一下午三点半交作业', '2026-11-30', '15:30', '中'],
    ['明晚八点开会', '2026-11-29', '20:00', '中'],
    ['低优先级：整理文件', null, null, '低'],
    ['高优先级：18:15写总结', null, '18:15', '高'],
    ['2026年12月5日上午十点背单词', '2026-12-05', '10:00', '中'],
  ]
  for (const [text, date, clock, priority] of cases) {
    const [task] = await parseTasks(text!, { now })
    assert.deepEqual([task.due_date, task.due_time, task.priority], [date, clock, priority], text!)
  }
})

test('午夜跨时区，按照选择的时区计算本地日期', async () => {
  const midnight = new Date('2026-11-28T17:05:00Z')
  const [shanghai] = await parseTasks('今天写作业', { now: midnight, timeZone: 'Asia/Shanghai' })
  const [newYork] = await parseTasks('今天写作业', { now: midnight, timeZone: 'America/New_York' })
  assert.equal(shanghai.due_date, '2026-11-29')
  assert.equal(newYork.due_date, '2026-11-28')
})

test('非任务留空，空白、超长输入与超限草稿会被拒绝', async () => {
  for (const text of ['今天天气很好', '写作业了吗？', '不用买牛奶']) assert.deepEqual(await parseTasks(text), [])
  await assert.rejects(parseTasks('  '), /任务内容/)
  await assert.rejects(parseTasks('读'.repeat(4001)), /任务内容/)
  await assert.rejects(parseTasks('读论文，'.repeat(51)), /分段/)
})

test('DeepSeek 请求使用独立凭据、JSON Output、当前日期时间和时区', async () => {
  const tasks = await parseTasks('读论文', {
    ...live,
    fetcher: async (url, options) => {
      assert.equal(url, 'https://api.deepseek.com/chat/completions')
      assert.equal(options?.method, 'POST')
      assert.equal(options?.redirect, 'error')
      assert.equal(options?.credentials, 'omit')
      assert.equal(options?.cache, 'no-store')
      assert.equal(new Headers(options?.headers).get('Authorization'), 'Bearer sample-token')
      const body = JSON.parse(String(options?.body))
      assert.equal(body.model, 'example-model')
      assert.deepEqual(body.response_format, { type: 'json_object' })
      assert.deepEqual(body.messages[1], { role: 'user', content: '读论文' })
      assert.match(body.messages[0].content, /2026-11-28 23:45:00，星期六，时区 Asia\/Shanghai/)
      assert.match(body.messages[0].content, /JSON/)
      return completion(JSON.stringify({ tasks: [draft] }))
    },
  })
  assert.deepEqual(tasks, [draft])
})

test('真实模式缺密钥和网络错误提供中文提示', async () => {
  await assert.rejects(parseTasks('读论文', { ...live, apiKey: '', fetcher: () => assert.fail('发起意外请求') }), /设置.*API Key/)
  await assert.rejects(parseTasks('读论文', { ...live, fetcher: async () => { throw new TypeError('failed to fetch') } }), /网络/)
})

for (const [status, message] of [[401, /鉴权/], [402, /余额/], [429, /频繁/], [503, /暂不可用/], [504, /超时/]] as const) {
  test(`HTTP ${status} 返回安全提示，不回显上游错误或密钥`, async () => {
    await assert.rejects(parseTasks('读论文', {
      ...live, fetcher: async () => new Response('diagnostic: sample-token', { status }),
    }), (error: Error) => message.test(error.message) && !error.message.includes('sample-token'))
  })
}

test('截断、空响应、错误 JSON 和部分无效的数组均不生成草稿', async () => {
  const invalid = [
    () => Response.json({}),
    () => completion('  '),
    () => completion('{}', 'length'),
    () => completion('not JSON'),
    () => completion('{"tasks":[{"title":"读论文"}]}'),
    () => completion(JSON.stringify({ tasks: [draft, { ...draft, category: '未知' }] })),
    () => completion(JSON.stringify({ tasks: [{ ...draft, due_date: '2026-02-30' }] })),
    () => completion(JSON.stringify({ tasks: [{ ...draft, status: '已完成' }] })),
  ]
  for (const getResponse of invalid) {
    await assert.rejects(parseTasks('读论文', { ...live, fetcher: async () => getResponse() }), /DeepSeek/)
  }
  assert.deepEqual(await parseTasks('你好', { ...live, fetcher: async () => completion('{"tasks":[]}') }), [])
})

test('连接一直未返回时终止请求并给出超时提示', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const request = parseTasks('读论文', {
    ...live,
    fetcher: (_url, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new TypeError('aborted')), { once: true })
    }),
  })
  t.mock.timers.tick(60_000)
  await assert.rejects(request, /超时/)
})
