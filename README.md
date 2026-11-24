# AI-Todo

AI-Todo 是在 macOS 本机运行的中文个人任务清单。写下一句话，预览拆分结果，调整后一次保存。默认使用本地 Mock 解析，可以直接体验整个流程。

## 首次启动

需要 Python 3.11+、Node.js 20.19+（20.x）或 22.12 及以上版本 和 npm。第一次启动需要联网下载依赖。在本项目目录运行：

```bash
./start.sh
```

打开 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**。保持终端运行，在终端按 Ctrl+C 退出。下次启动会复用虚拟环境和数据库。端口被占用时，可使用 `PORT=8010 ./start.sh`，并访问相应端口。

脚本会创建项目专用的 `.venv/` 和 `backend/.env`，安装依赖、构建网页，并用 FastAPI 同时提供页面和 API。服务绑定本机回环地址。

## 配置 DeepSeek

先运行一次启动脚本，或执行 `cp -n backend/.env.example backend/.env`。在本机编辑器中打开 `backend/.env`，修改下列配置并重启服务。

```dotenv
AI_MODE=deepseek
DEEPSEEK_API_KEY=在这里填入自己的密钥
DEEPSEEK_MODEL=deepseek-flash
APP_TIMEZONE=Asia/Shanghai
DATABASE_PATH=data/tasks.sqlite3
```

密钥从 [DeepSeek 开放平台](https://platform.deepseek.com/) 获取。启用真实模式后，点击「AI 整理任务」会把本次输入发送给 DeepSeek，并按平台规则计费。浏览器仅调用本机服务，配置文件已加入 Git 忽略列表。若要继续离线使用，设置 `AI_MODE=mock`，重启即可。两种模式共享已保存的清单。

后端调用 `POST https://api.deepseek.com/chat/completions`，使用环境变量指定的模型和 `response_format={"type":"json_object"}`。提示词包含 JSON 示例和本次调用的本地时间。空输出、截断内容和结构校验失败时，页面提示重试。[官方接入说明](https://api-docs.deepseek.com/) · [JSON Output](https://api-docs.deepseek.com/guides/json_mode/)

## 使用

1. 输入「明天写完数据库作业，周五之前提交社区实践周记，今天晚上背50个六级单词，还有空的时候看一下学长发来的论文。」
2. 点击「AI 整理任务」。检查预览中的四项任务，可以修改标题、说明、分类、优先级和截止日期或时间，也可以删除其中一项。
3. 确认保存后在清单中查看。勾选复选框完成任务，再次点击可恢复。清单支持编辑和删除。
4. 用导航切换今日任务、全部任务、即将到期、已完成或分类，使用清单工具筛选和排序。全部任务含已完成的历史记录。

「今日任务」显示配置时区下今天到期的待办。「即将到期」显示从明天到第七天（含）的待办。仅说「今天晚上」会记录今天，具体时刻留空。未给出的日期或时间也可在预览中手动补填。

Mock 是方便本地试用的中文规则解析器，适合明确的动作、常见日期和分句。复杂语义请切换到真实模式。AI 解析只产生候选项，每次保存前请核对日期、分类和拆分结果。

## 数据与配置

| 项目 | 位置或含义 |
| --- | --- |
| 数据库 | 默认 `backend/data/tasks.sqlite3`，首次启动自动初始化 |
| 更改数据库 | `DATABASE_PATH` 可为绝对路径，相对路径以 `backend/` 为起点 |
| 时区 | `APP_TIMEZONE` 接受 IANA 名称，如 `Asia/Shanghai` |
| 原始输入 | 随确认的任务保存在 SQLite 中 |
| 备份 | 关闭服务后复制整个 `backend/data/` 目录；恢复时同样先关闭服务 |
| 接口文档 | [本机 Swagger UI](http://127.0.0.1:8000/docs) |

## 开发与测试

开发时可以分别运行后端及 Vite。请先运行过一次 `./start.sh` 完成安装，并在切换到开发模式前停止该服务。

```bash
# 终端一，在仓库根目录
.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --port 8000

# 终端二
cd frontend
npm run dev
```

浏览器打开 Vite 在终端打印的地址。前端通过开发代理访问后端。

从仓库根目录运行全部验收测试：

```bash
.venv/bin/python -m pip install -r backend/requirements-dev.txt -r tests/requirements.txt
(cd frontend && npm ci && npm run build)
.venv/bin/python -m pytest -q backend/tests tests
```

浏览器测试优先使用 macOS 上安装的 Google Chrome。也可以设置 `CHROME_PATH` 指向浏览器可执行文件，或运行 `.venv/bin/python -m playwright install chromium` 安装配套浏览器。测试创建临时 SQLite 数据库和独立后端进程，无需真实密钥。

## 常见问题

- **真实模式提示缺少密钥**　确认修改的是 `backend/.env`，保存后重启后端。
- **余额、限流或超时提示**　按页面提示处理账户或网络问题，再次点击整理。清单中只会出现已确认保存的任务。
- **看不到刚保存的任务**　切换到「全部任务」并清除筛选。无截止日期的任务会出现在全部任务和相应分类中。
- **脚本无法启动**　检查 `python3 --version`、`node --version`、`npm --version` 以及终端报告的端口占用或依赖下载错误。

项目结构、接口约定与扩展入口见 [DEVELOPMENT.md](DEVELOPMENT.md)。
