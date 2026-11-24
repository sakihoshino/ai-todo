# AI-Todo V0.3 开发说明

开发分支为 `local-first`，起点为 V0.1 的 `16276a1`。同一套 Vue 页面可构建为独立 PWA 或原版 FastAPI 客户端。

## 运行路径

| 入口 | 数据访问 | 构建产物 |
| --- | --- | --- |
| `npm run dev` / `npm run build` | 浏览器 IndexedDB，默认离线规则解析 | `frontend/dist-local/`，含 manifest、图标和 service worker |
| `npm run dev:legacy` / `npm run build:legacy` | 同源 FastAPI，数据写入原 SQLite | `frontend/dist/`，由原有 `./start.sh` 使用 |

`frontend/src/workspace.ts` 根据构建模式接入数据和解析函数。旧版主页面、导航、任务编辑器、样式与原有业务字段在两种模式中复用。新增模型、存储、解析模块和设置/历史组件使用 TypeScript；原有 Vue 界面的编排逻辑继续使用 JavaScript。

### 主要文件

| 位置 | 职责 |
| --- | --- |
| `frontend/src/local/models.ts` | Zod 模型与类型：草稿、完整任务、补丁、历史事件和备份格式 |
| `frontend/src/local/repository.ts` | Dexie 版本、查询与排序、批量确认、事务、历史和备份读写 |
| `frontend/src/local/parser.ts`、`mock.ts` | 按应用时区解析日期、校验候选任务、处理 DeepSeek 错误 |
| `frontend/src/App.vue`、`components/` | 录入、预览、列表、导航、历史、备份与本页解析设置 |
| `backend/app/prompts/task_parser.txt` | 两个版本共用的提示词，Vite 仅读取此文件并编入静态客户端 |
| `frontend/vite.config.js` | PWA 插件、静态资源基路径、旧版代理与构建目录 |
| `scripts/export_sqlite.py` | 以只读连接导出旧版完整任务 JSON |
| `.github/workflows/pages.yml` | local-first 推送触发测试、静态检查与发布 |
| `frontend/tests/`、`tests/test_local_pwa.py` | TypeScript 单元测试、静态子路径和离线浏览器验收 |

## 存储与迁移

IndexedDB 名称为 `AI-Todo`，存储归属当前浏览器和站点来源。手机与电脑独立保存数据。任务沿用原 12 个字段、8 个分类、中文状态与优先级。UUID 在设备上生成，截止日期和时刻分别使用可空的日历值，审计时间使用带时区的 ISO 时间戳。

- **任务确认**　类型校验通过后，在同一 Dexie 写事务中保存任务、创建事件及批次回执。相同确认键和内容的重试返回现有记录；操作失败会整体回滚。
- **任务变更**　编辑、状态变更和删除与对应历史事件共同提交。历史保存任务标识、当时的标题、操作与时间，删除任务后仍能查看。历史用于回看，不提供撤销。
- **IndexedDB 升级**　保留 v1 的任务表定义；v2 增加索引、历史和批次表。升级事务为已有任务补记「导入」事件，字段和时间戳保留。后续结构调整新增 `version(n).upgrade(...)` 并用前一版本夹具测试。[Dexie 版本升级文档](https://dexie.org/docs/Version/Version.upgrade())
- **SQLite 迁入**　旧版 JSON 结构为 `{"tasks":[...]}`。手机读取并校验整个文件后批量导入。冲突任务按 ID 跳过，保留设备上的最新编辑。
- **整库备份**　版本化 JSON 包含任务与操作历史，历史事件使用稳定 ID 去重。备份在设备端生成，解析设置、密钥及内部确认回执均不导出。

## PWA 生命周期

Vite 在生产构建时生成 manifest、桌面图标与 Workbox 预缓存，覆盖 HTML、脚本、样式与本地图片。界面使用系统字体。service worker 的 scope、离线导航回退和静态资源均遵循 `PAGES_BASE_PATH`。首次联网完成安装之后，离线刷新也可从缓存加载整个清单。新构建的 worker 按浏览器生命周期接手，当前页面可先完成编辑。应用更新时，IndexedDB 的数据迁移由 Dexie 管理。

本地模式的任务和历史操作均由浏览器完成。启用在线解析后，只在用户点击整理时直接调用 DeepSeek。请求使用当前日期、时区、共享提示词和本次输入；模型输出经 Zod 校验后先展示预览。Key 仅保存在 Vue 当前页面内存中，在线接口响应不进入 PWA 缓存。

## 运行测试

从仓库根目录执行：

```bash
(cd frontend && npm ci && npm test && npm run build && npm run build:legacy)
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt -r tests/requirements.txt
.venv/bin/python -m pytest -q backend/tests tests
```

浏览器测试优先使用本机 Chrome；若未安装，请使用 `.venv/bin/python -m playwright install chromium webkit`。本地 PWA 测试会把生产构建挂在临时 HTTP 服务的 `/AI-Todo/` 子路径，并使用独立浏览器上下文。旧版回归和迁移测试使用临时 SQLite。所有自动化测试都可在没有付费密钥的情况下运行。

V0.2 基线通过 **20 项 TypeScript 测试**和 **59 项 Python/浏览器测试**（含原版 56 项）。验证了跨标签页重复确认、写入回滚、IndexedDB v1→v2 升级、SQLite→JSON→手机导入、离线冷刷新及增删改、状态与历史、DeepSeek 报文与错误、刷新后密钥清空。真实付费推理和公开站点发布待使用个人账户验证。旧版架构及验收记录见 [V0.1 开发说明](docs/v0.1-development.md)。

Chrome 使用普通临时用户配置验证了 PWA 安装条件，浏览器返回的安装错误列表为空。另在 WebKit 27.2 的 390×844 触屏视口实际完成断网刷新、新增任务、再次刷新后读取。Pages 子路径的离线导航、图标和入口均随同一构建发布。

## V0.3 发布维护

本版沿用现有任务模型、数据库名和版本。静态发布及手机安装手册见 [DEPLOYMENT.md](DEPLOYMENT.md)。Pages 工作流从 `local-first` 运行，只上传通过检查的静态目录。任务功能不需要部署后端服务。

V0.3 本机验收通过 99 项测试。新增的 20 项覆盖 14 个发布产物检查场景、4 个双引擎手机场景、一次实际 service worker 升级，以及一组上游失败测试。工作流安装 Chromium 和 WebKit，并构建 legacy 前端以运行旧版回归。手机验收使用隔离数据；发布和线上验收状态记录于部署手册。
