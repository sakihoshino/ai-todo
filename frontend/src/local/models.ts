import { z } from 'zod'

export const categorySchema = z.enum(['课程学习', '科学研究', '学生工作', '社会实践', '英语学习', '竞赛活动', '日常生活', '其他'])
export const prioritySchema = z.enum(['高', '中', '低'])
export const statusSchema = z.enum(['待完成', '已完成'])
export const rawInputSchema = z.string().min(1).max(4000).refine(value => Boolean(value.trim()), '请输入任务内容')
const dateSchema = z.iso.date().refine(value => !value.startsWith('0000'), '请输入有效日期')
const timestampSchema = z.iso.datetime({ offset: true })

export const draftSchema = z.strictObject({
  title: z.string().trim().min(1, '请输入任务名称').max(200),
  description: z.string().max(2000),
  category: categorySchema,
  due_date: dateSchema.nullable(),
  due_time: z.string().regex(/^(?:[01]\d|2[0-3]):[0-5]\d$/, '请输入有效时间').nullable(),
  priority: prioritySchema,
})

export const taskSchema = draftSchema.extend({
  id: z.uuid(),
  status: statusSchema,
  raw_input: rawInputSchema,
  created_at: timestampSchema,
  updated_at: timestampSchema,
  completed_at: timestampSchema.nullable(),
})

export const patchSchema = draftSchema.extend({ status: statusSchema }).partial()
  .refine(patch => Object.keys(patch).length > 0 && Object.values(patch).every(value => value !== undefined),
    '请提供要修改的字段')

export const historySchema = z.strictObject({
  id: z.uuid(),
  task_id: z.uuid(),
  title: z.string().min(1).max(200),
  action: z.enum(['创建', '编辑', '完成', '恢复', '删除', '导入']),
  timestamp: timestampSchema,
})

export const backupSchema = z.strictObject({
  format: z.literal('AI-Todo'),
  version: z.literal(2),
  tasks: z.array(taskSchema),
  history: z.array(historySchema),
})
export const legacyBackupSchema = z.strictObject({ tasks: z.array(taskSchema) })

export type TaskDraft = z.infer<typeof draftSchema>
export type Task = z.infer<typeof taskSchema>
export type TaskPatch = z.infer<typeof patchSchema>
export type HistoryEntry = z.infer<typeof historySchema>
export type Backup = z.infer<typeof backupSchema>
export type Category = z.infer<typeof categorySchema>
export type Priority = z.infer<typeof prioritySchema>
export type Status = z.infer<typeof statusSchema>

export type TaskQuery = {
  view?: 'all' | 'today' | 'upcoming' | 'completed'
  category?: Category
  status?: Status
  sort?: 'due_asc' | 'due_desc' | 'created_desc'
  today?: string
}
