# AI-Todo · 手机版 V0.3

用自然语言记下待办，确认后保存到这台手机的 IndexedDB。首次打开并完成离线缓存后，可从桌面图标打开，断网也能新增、整理、编辑、完成和删除任务。默认使用本地中文规则解析。需要在线 AI 时，可在当前页面启用 DeepSeek。

## 在本机试用

使用 Node.js 22.12+ 和 npm。在项目根目录执行：

```bash
cd frontend
npm ci
npm run build
npm run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

访问 **[http://127.0.0.1:4173](http://127.0.0.1:4173)**。这是生产构建的静态预览，可验证离线启动。日常开发用 `npm run dev` 启用 Vite 热更新。V0.3 的运行、安装与构建均可独立于 Python 服务。

## 发布到 GitHub Pages 并添加到手机桌面

配置 GitHub Pages 后，本版会从 `local-first` 自动发布。目前已完成本地验收，公开发布暂缓。GitHub Actions 会先运行测试和静态产物检查，再部署应用。手机使用 Pages 部署记录中的 HTTPS 地址。从主屏幕图标首次联网打开并缓存后，可关闭 Mac，继续在手机上管理任务。

iPhone 使用 Safari 的「分享 → 添加到主屏幕」，Android 使用 Chrome 的「⋮ → 安装应用 / 添加到主屏幕」。详细步骤、更新方式与真机验收见 [DEPLOYMENT.md](DEPLOYMENT.md)。

也可将 `dist-local/` 放到其他静态 HTTPS 服务。子路径部署时，用实际路径重新构建，例如 `PAGES_BASE_PATH=/AI-Todo/ npm run build`。首次安装和服务工作线程需要 HTTPS，本机开发可使用 localhost 或 127.0.0.1。[GitHub Pages 工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) · [PWA 安装条件](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable)

## 记录任务与使用 DeepSeek

- **直接记录**　点击「新增任务」填写名称即可保存。
- **拆分后确认**　输入「明天写完数据库作业，今天晚上背50个六级单词，有空时读论文」，点击「AI 整理任务」。可以逐项修改、移除，再统一保存。默认时区为 Asia/Shanghai，未给具体时间时保留空值。
- **在线解析**　在右上角「解析设置」选择 DeepSeek，输入个人 API Key 和模型名（默认 `deepseek-flash`）。只有点击整理时，浏览器才会把本次输入和解析提示词发往 DeepSeek，费用按个人账户计费。密钥仅保留在本页内存中，刷新后需重新配置。请勿在代码、仓库变量或 Vite 构建环境中填写个人密钥。
- **查看与管理**　侧栏支持日期、状态、分类筛选；「即将到期」指明天起七天内。清单支持截止日期排序和完成后恢复。手机上点击左上角打开导航。

真实模式采用官方聊天接口与 JSON Output。上游异常时会保留输入，用户可重试或切回本地规则。[DeepSeek 官方说明](https://api-docs.deepseek.com/) · [JSON Output](https://api-docs.deepseek.com/guides/json_mode/)

## 操作历史、备份与迁移

「操作历史」可查看创建、编辑、完成、恢复、删除和导入记录，并导出任务和历史的 JSON 备份。清理浏览器网站数据、切换浏览器、换手机或更改站点来源，都可能需要重新导入。建议在日常使用的桌面图标中记录任务，并在清理或迁移前导出备份。备份含任务正文和原始输入，应按个人文件保管。

**迁入 V0.1 任务**　从项目根目录执行以下命令。可以把第一个路径替换为 SQLite 备份的实际位置，输出路径须为新文件。

```bash
mkdir -p backups
python3 scripts/export_sqlite.py backend/data/tasks.sqlite3 backups/legacy-tasks.json
```

将 JSON 传到手机，在「操作历史 → 导入任务」中选择文件。导入保留 ID、分类、状态、原始输入和时间戳，已有 ID 会跳过。相同入口支持 V0.2 导出的 JSON。SQLite 文件仅需在迁移旧数据时读取。

## 继续使用 V0.1

在项目根目录运行 `./start.sh`，访问 [http://127.0.0.1:8000](http://127.0.0.1:8000)。原有后端配置及 SQLite 数据继续使用，手机清单与旧库可通过文件迁移。[V0.1 使用说明](docs/v0.1.md)

测试命令、数据库分层、升级机制和验收记录见 [DEVELOPMENT.md](DEVELOPMENT.md)。
