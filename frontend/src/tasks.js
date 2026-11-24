export const categories = [
  ['课程学习', '#839b78'], ['科学研究', '#899eb3'],
  ['学生工作', '#b39473'], ['社会实践', '#ad877c'],
  ['英语学习', '#91a69b'], ['竞赛活动', '#b3a15c'],
  ['日常生活', '#a390ae'], ['其他', '#a3a39b'],
]
export const priorities = ['高', '中', '低']
export const examples = [
  { category: '课程学习', text: '明天写完数据库作业' },
  { category: '英语学习', text: '今天晚上背 50 个六级单词' },
  { category: '科学研究', text: '有空时读一下学长发来的论文' },
]

export async function api(path, options = {}) {
  let response
  try {
    response = await fetch('/api/' + path, {
      ...options,
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers,
      },
    })
  } catch {
    throw new Error('无法连接服务，请检查本地服务是否正在运行。')
  }
  if (response.status === 204) return null
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    let error = payload?.detail
    if (Array.isArray(error)) error = '任务字段格式有误，请检查名称、日期和时间。'
    throw new Error(typeof error === 'string' ? error : '请求失败，请稍后重试。')
  }
  if (!payload) throw new Error('服务返回了无效数据，请重试。')
  return payload
}

// Work in calendar days so browser timezone and daylight-saving changes cannot shift a task.
export function dayOffset(date, today) {
  return (Date.parse(date + 'T00:00:00Z') - Date.parse(today + 'T00:00:00Z')) / 86400000
}

export function editableFields(task) {
  const {title, description, category, due_date, due_time, priority} = task
  return {title: title.trim(), description: description || '', category, due_date: due_date || null,
    due_time: due_time?.slice(0, 5) || null, priority}
}
