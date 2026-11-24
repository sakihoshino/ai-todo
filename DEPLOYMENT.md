# GitHub Pages 发布与手机安装

**手机入口**　[打开 AI-Todo](https://sakihoshino.github.io/ai-todo/)

**源码与发布记录**　[公开仓库](https://github.com/sakihoshino/ai-todo) · [Pages 工作流](https://github.com/sakihoshino/ai-todo/actions/workflows/pages.yml)

## 发布内容

发布来源为 `local-first` 分支。[工作流](.github/workflows/pages.yml) 会在该分支收到推送时运行，也可在 Actions 页面手动运行。工作流安装锁定依赖，运行前端、后端和浏览器回归测试，按 Pages 提供的路径构建 V0.3，并检查静态文件后部署。

线上只需要 `frontend/dist-local/` 中的 HTML、样式、JavaScript、图标、插画、manifest 和离线缓存程序。公开仓库的源码、提交历史及 Actions 日志对公众可见。旧 FastAPI 版本仍可在本地使用。手机的 IndexedDB、旧数据库和备份文件保存在各自设备上。

## 首次发布

如本机尚未登录 GitHub CLI，可在准备发布时运行 `gh auth login --hostname github.com --git-protocol https --web`，按终端提示在 GitHub 官方页面完成浏览器授权，再用 `gh auth status` 核对账号。CLI 登录与创建公开仓库、公开发布网站是独立的操作。[GitHub CLI 登录说明](https://cli.github.com/manual/gh_auth_login)

仓库管理员在 **Settings → Pages → Build and deployment** 把来源设为 **GitHub Actions**，然后推送 `local-first` 或在 Actions 中从该分支手动运行 **Publish local-first PWA**。手动运行入口要求工作流文件存在于默认分支。Pages 部署成功后的 **Deploy to Pages** 环境链接就是手机入口，使用 HTTPS。仓库名有大小写之分，请使用 GitHub 给出的完整地址。

工作流读取 Pages 的 `base_path`，使 Vite 资源、manifest、桌面图标和 service worker 使用同一项目子路径。GitHub 托管运行所需的全部静态文件，Mac 关机后手机仍可访问。无需在 GitHub 设置 DeepSeek 密钥。[GitHub Pages 自定义工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

## 在手机上安装

- **iPhone**　用 Safari 打开已发布的 HTTPS 地址，点分享 →「添加到主屏幕」。如系统提供「作为网页 App 打开」，启用后点「添加」。首次从桌面图标打开时保持联网。[Apple 安装说明](https://support.apple.com/guide/iphone/iphea86e5236/ios)
- **Android**　用 Chrome 打开同一地址，在 ⋮ 菜单点「添加到主屏幕」或「安装应用」，按提示安装，再从图标启动一次。[Chrome 安装说明](https://support.google.com/chrome/answer/9658361?co=GENIE.Platform%3DAndroid)
- **检查离线启动**　在桌面版应用中创建一项测试任务，退出应用，打开飞行模式，再从图标启动。检查能否查看、编辑和完成该任务。离线时使用「本地规则解析」或直接新增任务。
- **检查系统界面**　在真机上试一次中文输入、日期选择、键盘收起与提交，再试横屏、侧栏和底部系统手势。检查内容和操作按钮是否被系统栏遮挡。
- **数据备份**　在「操作历史」导出 JSON 并确认能在手机文件管理器找到。清理站点数据、换浏览器或换设备前请备份。建议始终在同一个安装入口记录任务。

## 更新版本

在项目根目录运行以下命令，确认变更和测试通过后再推送：

```bash
git switch local-first
git status
(cd frontend && npm ci && npm test && npm run build && npm run build:legacy)
python3 scripts/check_release.py frontend/dist-local
.venv/bin/python -m pytest -q backend/tests tests
git push origin local-first
```

推送只发布已提交到分支的更改。可用 `gh run list --workflow pages.yml --branch local-first` 查看对应提交，再用 `gh run watch RUN_ID --exit-status` 等待完成。构建、测试或安全检查失败时，查看失败步骤并修复后再次推送。故障回退可通过 `git revert` 撤销有问题的提交并重新发布。

手机联网打开一次后，新 service worker 下载新资源。保存当前编辑，关闭同一站点的所有浏览器标签和已安装应用窗口，再重新打开。若系统尚未发现版本更新，稍后联网重开。保留原 HTTPS 来源、应用路径、manifest ID 与数据库名。应用资源缓存在 Cache Storage，个人任务在 IndexedDB，普通版本更新会保留已有任务。首次更改数据库结构时需要版本迁移测试。

## DeepSeek 验证口径

手机在「解析设置」中输入的 Key 仅保留在当前页面内存。点击「AI 整理任务」时，浏览器向官方 HTTPS 接口发送 Bearer 请求头和 JSON Output 请求。错误提示、预览及写入边界可用模拟响应验收；CORS 预检和无效凭据返回 401 可单独验证真实网络连通性。一次成功的真实模型推理需要用户自己的有效密钥和账户余额。不要把密钥粘贴到终端命令、仓库或 Actions 中。

## 本地复验

`npm run preview` 提供当前 Mac 的本地预览，仅适用于本机检查。浏览器测试以临时静态服务模拟 Pages 子路径，通过关闭网络、更新服务工作线程和重开页面验证缓存与数据。线上验收使用 GitHub 输出的实际地址，并在隔离的浏览器配置中新增、编辑、完成、删除测试任务以及往返导入备份，避免影响自己的清单。

## 本次发布状态

V0.3 已通过本地发布检查，公开仓库已创建。站点采用 GitHub 提供的 HTTPS 域名，Pages 来源为 GitHub Actions，发布分支为 `local-first`。

- 本机测试共 99 项通过（20 项 TypeScript、79 项 Python 和浏览器测试），包含原有 79 项。
- 两次独立构建在相同来源和子路径完成 service worker 切换，更新前后的 IndexedDB 记录一致。另实测关闭静态服务、退出 Chrome、断网重开后，任务可读取、完成并刷新保留。
- iPhone 13 / Pixel 7 的模拟视口通过了 WebKit / Chromium 的触屏和离线测试。真实安装、系统键盘、屏幕安全区与后台回收仍需真机验收。应用沿用侧栏导航。
- 使用示例 GitHub Pages 来源发往 DeepSeek 的真实 CORS 预检返回 200，允许 POST、Authorization 和 Content-Type。浏览器通过模拟来源的 HTTPS 页面、使用故意无效的凭据向官方端点发出请求，成功读取跨域 401。模型名、JSON Output、预览与异常通过受控响应验证，尚未在实际发布域名用有效密钥完成推理。
- 发布检查只允许本项目的 12 个必要静态文件。当前构建通过文件、图片元数据及常见凭据检查。`.env`、旧库及备份继续保留在本地，并由 Git 忽略。

本次推送前复核了 V0.3 基线的三个提交、全部 121 个本地 Git 对象、59 个跟踪文件和 12 个静态产物。检查未发现真实凭据、个人邮箱、本机用户目录或私有数据库进入发布内容。三张旧图标带有文件系统时间戳；当前图标及发布产物已移除该元数据，旧提交保留原历史。
