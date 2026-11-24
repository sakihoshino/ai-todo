# AI-Todo V0.1 开发说明

## 代码布局

```text
AI-Todo/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口、路由、异常处理和网页静态资源
│   │   ├── config.py                # 后端配置与 IANA 时区
│   │   ├── models.py                # 请求、候选任务和持久化任务的 Pydantic 模型
│   │   ├── parser.py                # DeepSeek JSON Output 调用及返回值校验
│   │   ├── mock_parser.py           # 本地中文规则
│   │   ├── prompts/task_parser.txt  # 可独立调整的系统提示词
│   │   └── database.py              # SQLite 初始化、查询及写入事务
│   ├── tests/                       # API、数据库、解析规则及模拟上游异常测试
│   ├── .env.example
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/
│   ├── src/                         # Vue 页面、任务编辑器、导航、API 客户端和样式
│   ├── public/                      # 站点图标及本地手帐插画
│   ├── vite.config.js
│   └── package.json / package-lock.json
├── tests/                           # HTTP 进程重启及桌面、移动视口验收
├── start.sh
├── README.md
└── DEVELOPMENT.md
```

## 数据流

用户输入 → `/parse` → 本地 Mock 或 DeepSeek → Pydantic 校验 → Vue 预览 → 用户编辑、移除并确认 → `/batch` → SQLite 事务 → 清单。

解析模块只接收输入、配置和调用时刻。它返回六个可编辑字段。后端在确认保存时生成 UUID、初始状态、创建和更新时间，并将本次原始输入附到每项任务。批量写入使用单个事务，任一项失败都会回滚。完成操作设置 `completed_at`，恢复会将其清空。

截止日期和时间是用户时区下的日历值，分别保存为 ISO 日期和 24 小时制时刻，均允许为空。审计时间戳使用带 UTC 偏移的时间。改变显示时区后，相同的截止日期仍是原先填写的日历日，筛选「今天」按新的时区计算。

## API 约定

| 方法和路径 | 请求与返回 |
| --- | --- |
| `GET /api/health` | 服务状态、解析模式、密钥是否已配置、时区与本地日期 |
| `POST /api/tasks/parse` | 输入 `{"raw_input":"明天交作业"}`，返回 `{"mode":"mock","tasks":[…]}`；没有可执行任务时返回空数组 |
| `POST /api/tasks/batch` | 输入 `{"raw_input":"…","tasks":[…]}`，返回已保存的 `{"tasks":[…]}`；可传 `Idempotency-Key` 避免相同请求重试时重复入库 |
| `GET /api/tasks` | 返回 `{"tasks":[…]}`；支持组合筛选及排序 |
| `GET /api/tasks/{id}` | 返回一项完整任务 |
| `PATCH /api/tasks/{id}` | 仅传需修改的字段；清除日期或时间时显式传 `null`。返回更新结果 |
| `DELETE /api/tasks/{id}` | 成功返回 204 |

清单的 `view` 接受 `all`、`today`、`upcoming`、`completed`。`category`、`status` 使用界面上的中文值。`sort` 接受 `due_asc`、`due_desc`、`created_desc`。按截止时间排序时，日期为空的任务排在有日期的任务之后。任务输入至多 4,000 字符，单批至多 50 项。

## 当前进度与维护入口

V0.1 包含自然语言解析、人工确认、任务管理、清单导航、持久化、错误提示和可重复运行的验收测试。生产构建由一个本地 HTTP 进程提供。修改前端后重新运行启动脚本，或使用 Vite 的开发服务器。修改后端配置或提示词后重启后端。

- **调整解析行为**　修改提示词，在 `backend/tests/` 添加覆盖该语义的解析样例。DeepSeek 模型可通过后端配置切换。Mock 的日期、时刻与关键词规则在单独模块维护。
- **增加分类或任务字段**　同步更新 Pydantic 模型、解析提示词、Mock 规则、Vue 表单和验收用例。涉及已保存数据时，应先添加数据库版本迁移并在旧库副本上测试。
- **扩展筛选**　在数据库查询和前端视图中保持相同的日期边界和空值排序语义。数据量增长后可以添加分页。
- **维护上游兼容性**　自动化测试通过模拟 HTTP 响应检查成功、空输出、字段不合法和上游错误等路径。更换模型时，可用真实账户运行示例并在预览中核对拆分与日期。

## 插画资产

`frontend/public/desk-note.webp` 由内置 imagegen 生成后压缩为 WebP，随站点本地加载。画面提示为米白纸面上的打开的任务手帐、铅笔与橄榄枝，细墨线和低饱和水彩，横向构图。

## 本机验收记录

2026-11-24 在 Apple Silicon macOS、Python 3.12.9、Node.js 26.10.0 和 Chrome 156 上验证。共 56 项自动化测试通过，其中 50 项覆盖后端与解析，6 项覆盖真实 HTTP 进程和浏览器。测试使用独立临时数据库。

| 验收场景 | 已观察到的结果 |
| --- | --- |
| 单项、多项与相对日期 | 单项输入得到一项；README 中的长句得到作业、周记、单词和论文四项；跨周日期用例通过 |
| 日期、时间留空 | 论文条目无日期仍能入库；模糊的“晚上”未转换为具体时刻 |
| 预览再保存 | 修改预览标题、移除候选项；确认前库为空，确认后只保存保留的版本 |
| 日常操作与历史清单 | 浏览器完成勾选、查看已完成、恢复、改名、删除、分类筛选和截止日期排序 |
| 持久化 | 浏览器刷新保留修改；停止后端进程后，使用同一 SQLite 文件启动新进程，条数、ID 和内容一致 |
| 错误路径 | 模拟鉴权、余额不足、限流、断网、超时、截断和无效 JSON；余额不足时清单为空，页面保留输入 |
| 移动布局 | 390×844 触屏视口完成主要操作；320、390、768 和 1440 像素宽度未出现页面横向溢出 |
| 运行与依赖 | 启动脚本、Vite 开发代理、生产构建、pip check、npm 依赖检查均通过 |

真实模式的请求结构与错误路径通过模拟 HTTP 传输验证。未提供 DeepSeek 密钥，本次未验证付费账户的线上推理结果。手机测试使用 Chrome 移动视口。

<details>
<summary>本地手帐插画的生成提示</summary>

A refined single editorial spot illustration for a minimalist personal task manager. Isolated still life of an open ivory paper notebook with a dark muted forest-green linen back cover and a few delicate ruled checklist doodles without text on its pages, a slender muted ochre pencil across the right page, a graceful olive twig with sage leaves extending diagonally behind the notebook. Three-quarter overhead perspective with the front corner pointing down-left. Hand-inked fine charcoal contours, muted watercolor color fills with delicate hatching and minimal soft grounding marks. Perfectly plain uniform warm offwhite background all the way to image edges (no desk or background scenery). Horizontal wide 3:2 composition, one cohesive object group centered filling most of frame, generous breathing space all around. Contemporary Japanese stationery illustration, warm quiet morning palette, no lettering, no border.

</details>
