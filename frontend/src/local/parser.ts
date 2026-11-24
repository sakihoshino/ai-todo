import { z } from 'zod'
import { draftSchema, rawInputSchema, type TaskDraft } from './models.ts'
import { parseMock } from './mock.ts'

const endpoint = 'https://api.deepseek.com/chat/completions'
const parsedTasks = z.strictObject({ tasks: z.array(draftSchema).max(50) })
const chatResponse = z.object({
  choices: z.array(z.object({
    finish_reason: z.string(), message: z.object({ content: z.string().nullable() }),
  })).min(1),
})

export interface ParseOptions {
  mode?: 'mock' | 'deepseek'
  /** Supplied by the current page, never copied into drafts or persistent storage. */
  apiKey?: string
  model?: string
  timeZone?: string
  systemPrompt?: string
  now?: Date
  fetcher?: typeof fetch
}

const failureMessages: Record<number, string> = {
  400: 'DeepSeek 拒绝了请求，请检查模型名称。',
  401: 'DeepSeek 鉴权失败，请检查 API Key。',
  402: 'DeepSeek 账户余额不足，请充值后重新整理。',
  403: '当前 API Key 无权使用此服务，请检查账户权限。',
  408: 'DeepSeek 响应超时，请稍后重试。',
  422: 'DeepSeek 不支持当前请求参数，请检查模型配置。',
  429: 'DeepSeek 请求过于频繁，请稍后重试。',
  504: 'DeepSeek 响应超时，请稍后重试。',
}

function localTime(now: Date, timeZone: string) {
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'long',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  }).formatToParts(now)
  const values = Object.fromEntries(parts.map(p => [p.type, p.value]))
  const date = `${values.year}-${values.month}-${values.day}`
  const clock = `${values.hour}:${values.minute}:${values.second}`
  return { date, context: `本地时间 ${date} ${clock}，${values.weekday}，时区 ${timeZone}。` }
}

function readTasks(content: string): TaskDraft[] {
  let result
  try {
    result = parsedTasks.parse(JSON.parse(content))
  } catch {
    throw new Error('DeepSeek 返回的 JSON 或任务字段无效，请重新整理。')
  }
  return result.tasks
}

async function parseDeepSeek(rawInput: string, options: ParseOptions, timeContext: string) {
  const key = options.apiKey?.trim()
  if (!key) throw new Error('请先在设置中填写 DeepSeek API Key，或切换为 Mock 模式。')
  if (!/^[!-~]+$/.test(key)) throw new Error('DeepSeek API Key 格式有误，请检查后重试。')
  if (!options.systemPrompt?.trim()) throw new Error('解析提示词未加载，请刷新页面后重试。')

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 60_000)
  try {
    let response: Response
    try {
      response = await (options.fetcher ?? fetch)(endpoint, {
        method: 'POST', cache: 'no-store', credentials: 'omit', redirect: 'error', referrerPolicy: 'no-referrer',
        headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          model: options.model?.trim() || 'deepseek-flash',
          messages: [
            { role: 'system', content: options.systemPrompt + '\n' + timeContext },
            { role: 'user', content: rawInput },
          ],
          response_format: { type: 'json_object' }, thinking: { type: 'disabled' }, stream: false, max_tokens: 8192,
        }),
      })
    } catch {
      throw new Error('无法连接 DeepSeek，请检查网络后重试。离线时可使用 Mock 模式。')
    }
    if (!response.ok) throw new Error(failureMessages[response.status] || 'DeepSeek 服务暂不可用，请稍后重试。')

    const payload = chatResponse.safeParse(await response.json().catch(() => null))
    if (!payload.success) throw new Error('DeepSeek 返回的响应格式无效，请重新整理。')
    const choice = payload.data.choices[0]
    if (choice.finish_reason !== 'stop') throw new Error('DeepSeek 未完整输出，请缩短输入后重试。')
    if (!choice.message.content?.trim()) throw new Error('DeepSeek 返回空内容，请重新整理。')
    return readTasks(choice.message.content)
  } catch (error) {
    if (controller.signal.aborted) throw new Error(failureMessages[408])
    throw error
  } finally {
    clearTimeout(timer)
  }
}

/** Produces unsaved previews. Only the explicit confirmation path persists tasks. */
export async function parseTasks(rawInput: string, options: ParseOptions = {}): Promise<TaskDraft[]> {
  if (!rawInputSchema.safeParse(rawInput).success) throw new Error('请输入 1 至 4000 字的任务内容。')
  const time = localTime(options.now ?? new Date(), options.timeZone ?? 'Asia/Shanghai')
  if (options.mode === 'deepseek') return parseDeepSeek(rawInput, options, time.context)
  const result = parsedTasks.safeParse({ tasks: parseMock(rawInput, time.date) })
  if (!result.success) throw new Error('这段内容生成的任务过多或过长，请分段整理。')
  return result.data.tasks
}
