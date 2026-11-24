// Conservative offline rules shared in meaning with the V0.1 Python parser.
import type { TaskDraft } from './models.ts'

const weekdays = '一二三四五六日'
const relativeDays: Record<string, number> = {
  今天: 0, 今日: 0, 今晚: 0, 今早: 0, 明天: 1, 明日: 1, 明晚: 1, 明早: 1, 后天: 2, 大后天: 3,
}
const day = /(?<iso>\d{4}-\d{2}-\d{2})|(?:(?<year>\d{4})年)?(?<month>\d{1,2})月(?<day>\d{1,2})[日号]|(?<relative>大后天|今天|今日|今晚|今早|明天|明日|明晚|明早|后天)|(?<week>本|这|下)?(?:周|星期)(?<weekday>[一二三四五六日天])/
const period = '凌晨|清晨|早晨|早上|上午|中午|下午|傍晚|晚上|晚间|今晚|明晚|今早|明早'
const number = '[0-9]{1,2}|[零一二两三四五六七八九十]{1,3}'
const clock = new RegExp(
  `(?<period>${period})?\\s*(?:(?<hour>${number})[点时](?:(?<half>半)|(?<minute>${number})分?)?` +
  `|(?<isoHour>[0-9]{1,2})[:：](?<isoMinute>[0-9]{2}))(?![0-9])`,
)
const verbs =
  '写|做|交|提交|完成|背|发|阅读|读|看|复习|预习|整理|参加|安排|准备|买|购买|学习|练习|' +
  '打扫|清理|打卡|打电话|联系|回复|打印|制作|录入|更新|修复|检查|修改|设计|实现|测试|' +
  '预约|领取|取|寄|跑步|散步|运动|锻炼|洗|收拾|归还|还书|缴|交费|去|回|记|分析|' +
  '统计|处理|下载|上传|翻译|报名|练|汇报|开会|上课|补|收集|讨论|面试|寄送'
const action = new RegExp(`^(?:${verbs})`)
const clauses = new RegExp(`[，,。；;！!\\n]+|然后|接着|另外|还有|并且|(?:以及|[、并和])(?=(?:${verbs}))`)
const prefix = /^(?:(?:请(?:帮我)?|帮我|提醒我|记得|记一下|我(?:打算|计划|准备|想要|想|要|需要)|需要|待办[：:]?|先|再|还要|还需|在|于|要|将于|之前|以前|前|有空(?:的时候|时)?|空的时候)\s*)+/
const qualifiers = new RegExp(`${period}|优先级[为是：:]?[高中低]|[高中低]优先级|不紧急|紧急|不着急`, 'g')
const categories: [TaskDraft['category'], RegExp][] = [
  ['英语学习', /六级|四级|单词|英语|雅思|托福|英文/],
  ['社会实践', /社会实践|社区实践|志愿|实践周记/],
  ['竞赛活动', /竞赛|比赛|数模|建模赛|挑战杯/],
  ['学生工作', /班会|学生会|班委|团支部|团日/],
  ['科学研究', /论文|文献|实验|课题|科研/],
  ['课程学习', /作业|课程|上课|预习|复习|考试|章节|课本/],
  ['日常生活', /买|做饭|运动|跑步|散步|吃饭|打扫|还书|洗|快递|购物|锻炼/],
]

function validDay(text: string): string | null {
  const dt = new Date(text + 'T00:00:00Z')
  return Number.isFinite(+dt) && dt.toISOString().slice(0, 10) === text ? text : null
}

function resolveDay(groups: Record<string, string>, today: string): string | null {
  if (groups.iso) return validDay(groups.iso)
  if (groups.month) {
    const year = groups.year || today.slice(0, 4)
    return validDay(`${year}-${groups.month.padStart(2, '0')}-${groups.day.padStart(2, '0')}`)
  }

  // Operate on abstract calendar days in UTC. "Tomorrow" may not be 24 local hours away.
  const dt = new Date(today + 'T00:00:00Z')
  let offset: number
  if (groups.relative) {
    offset = relativeDays[groups.relative]
  } else {
    const weekday = (dt.getUTCDay() + 6) % 7
    offset = weekdays.indexOf(groups.weekday.replace('天', '日')) - weekday
    if (groups.week === '下') offset += 7
    if (!groups.week && offset < 0) offset += 7
  }
  dt.setUTCDate(dt.getUTCDate() + offset)
  return dt.toISOString().slice(0, 10)
}

function chineseNumber(raw: string): number {
  if (/^\d+$/.test(raw)) return Number(raw)
  const units = '零一二三四五六七八九'
  const text = raw.replace(/两/g, '二')
  if (text.includes('十')) {
    const [tens, ones] = text.split('十')
    return (tens ? units.indexOf(tens) : 1) * 10 + (ones ? units.indexOf(ones) : 0)
  }
  return Number([...text].map(char => units.indexOf(char)).join(''))
}

function resolveClock(groups: Record<string, string>): string | null {
  let hour = chineseNumber(groups.hour || groups.isoHour)
  const minute = groups.half ? 30 : chineseNumber(groups.minute || groups.isoMinute || '0')
  if (['下午', '傍晚', '晚上', '晚间', '今晚', '明晚'].includes(groups.period) && hour >= 1 && hour < 12) hour += 12
  if (groups.period === '中午' && (hour === 1 || hour === 2)) hour += 12
  if (groups.period === '凌晨' && hour === 12) hour = 0
  if (hour < 0 || hour >= 24 || minute < 0 || minute >= 60) return null
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

export function parseMock(raw: string, today: string): TaskDraft[] {
  const tasks: TaskDraft[] = []
  for (const clause of raw.split(clauses)) {
    const text = clause.replace(/^[\s“”"]+|[\s“”"]+$/g, '')
    if (!text || /[？?]|(?:吗|呢)$|不用|不需要|不要|无需|已经|不打算/.test(text)) continue
    const dayMatch = text.match(day)
    const clockMatch = text.match(clock)
    let title = text
    if (clockMatch) title = title.replace(clockMatch[0], '')
    if (dayMatch) title = title.replace(dayMatch[0], '')
    title = title.replace(qualifiers, '').trim().replace(prefix, '').replace(/^[\s：:，,]+|[\s：:，,]+$/g, '')
    if (!action.test(title)) continue

    let priority: TaskDraft['priority'] = '中'
    if (/低优先级|优先级[为是：:]?低|不着急|不紧急/.test(text)) priority = '低'
    else if (/高优先级|优先级[为是：:]?高|紧急/.test(text)) priority = '高'
    tasks.push({
      title, description: text !== title ? text : '', priority,
      category: categories.find(([, words]) => words.test(title))?.[0] ?? '其他',
      due_date: dayMatch?.groups ? resolveDay(dayMatch.groups, today) : null,
      due_time: clockMatch?.groups ? resolveClock(clockMatch.groups) : null,
    })
  }
  return tasks
}
