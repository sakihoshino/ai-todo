"""在 GitHub Pages 风格的子路径运行生产构建，不启动 FastAPI。"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
from threading import Thread

import pytest
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[1]


class QuietStaticFiles(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


@pytest.fixture(scope="module")
def static_site(tmp_path_factory):
    import os

    root = tmp_path_factory.mktemp("static-pages")
    subprocess.run(
        ["npm", "run", "build", "--", "--outDir", str(root / "AI-Todo")],
        env={**os.environ, "PAGES_BASE_PATH": "/AI-Todo/"},
        cwd=ROOT / "frontend", check=True,
    )
    handler = partial(QuietStaticFiles, directory=str(root))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}/AI-Todo/"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


def test_installed_shell_offline_lifecycle(browser, static_site):
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, locale="zh-CN",
    )
    page = context.new_page()
    requests, errors = [], []
    page.on("request", lambda request: requests.append(request.url))
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(static_site)
        expect(page.get_by_role("button", name="新增任务", exact=True)).to_be_visible()
        manifest = page.locator('link[rel="manifest"]').evaluate("(link) => link.href")
        assert manifest == static_site + "manifest.webmanifest"
        assert page.request.get(manifest).json()["display"] == "standalone"
        assert page.evaluate("async () => (await navigator.serviceWorker.ready).scope") == static_site

        # The worker now has the whole shell. Reload with the network disabled.
        context.set_offline(True)
        page.reload()
        expect(page.get_by_role("button", name="新增任务", exact=True)).to_be_visible()
        page.get_by_placeholder("今天有什么想做的？直接告诉我就好。").fill("明天写完数据库作业，读论文")
        page.get_by_role("button", name="AI 整理任务", exact=True).click()
        expect(page.get_by_label("预览任务名称")).to_have_count(2)
        page.get_by_role("button", name="确认保存", exact=True).click()
        rows = page.get_by_test_id("task-row")
        expect(rows).to_have_count(2)
        page.get_by_role("button", name="新增任务", exact=True).click()
        page.get_by_label("任务名称", exact=True).fill("离线整理手机照片")
        page.get_by_role("button", name="保存任务", exact=True).click()
        extra = rows.filter(has_text="离线整理手机照片")
        expect(extra).to_be_visible()
        extra.get_by_label("标记完成", exact=True).click()
        expect(extra.get_by_label("恢复待办")).to_be_visible()
        extra.get_by_label("恢复待办").click()
        extra.get_by_label("编辑任务", exact=True).click()
        page.get_by_label("任务名称", exact=True).fill("备份手机照片")
        page.get_by_role("button", name="保存修改").click()
        renamed = rows.filter(has_text="备份手机照片")
        expect(renamed).to_be_visible()
        page.reload()
        expect(renamed).to_be_visible()
        renamed.get_by_label("删除任务", exact=True).click()
        page.get_by_role("button", name="确认删除").click()
        expect(rows).to_have_count(2)
        page.get_by_role("button", name="打开导航").click()
        page.get_by_role("button", name="操作历史", exact=True).click()
        expect(page.get_by_text("备份手机照片", exact=True).first).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert not [url for url in requests if "/api/" in url or "api.deepseek.com" in url]
        assert errors == []
    finally:
        context.close()


def test_real_parser_preview_without_persisting_credentials(browser, static_site):
    import json

    context = browser.new_context()
    page = context.new_page()
    upstream = []
    draft = {
        "title": "整理实验结果", "category": "科学研究", "priority": "中",
        "description": "", "due_date": None, "due_time": None,
    }

    def respond(route):
        upstream.append(route.request)
        route.fulfill(json={"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"tasks": [draft]}, ensure_ascii=False),
        }}]})

    try:
        page.route("https://api.deepseek.com/chat/completions", respond)
        page.goto(static_site)
        page.get_by_role("button", name="解析设置").click()
        page.get_by_label("解析方式").select_option("deepseek")
        page.get_by_label("DeepSeek API Key").fill("test-session-key")
        page.get_by_role("button", name="应用设置").click()
        page.get_by_placeholder("今天有什么想做的？直接告诉我就好。").fill("整理实验结果")
        page.get_by_role("button", name="AI 整理任务").click()
        expect(page.get_by_label("预览任务名称")).to_have_value("整理实验结果")
        expect(page.get_by_test_id("task-row")).to_have_count(0)
        assert len(upstream) == 1
        assert upstream[0].headers["authorization"] == "Bearer test-session-key"
        assert upstream[0].post_data_json["response_format"] == {"type": "json_object"}
        page.get_by_role("button", name="确认保存").click()
        expect(page.get_by_test_id("task-row")).to_have_count(1)
        page.reload()
        expect(page.get_by_test_id("task-row")).to_have_count(1)
        page.get_by_role("button", name="解析设置").click()
        expect(page.get_by_label("解析方式")).to_have_value("mock")
        page.get_by_label("解析方式").select_option("deepseek")
        expect(page.get_by_label("DeepSeek API Key")).to_have_value("")
        assert "test-session-key" not in str(context.storage_state(indexed_db=True))
    finally:
        context.close()


def test_sqlite_to_mobile_backup(browser, static_site, server, tmp_path):
    import json
    import sys
    import httpx

    # Create a real V0.1 task with the same path a desktop user follows.
    with httpx.Client(base_url=server.url, trust_env=False) as api:
        old = api.post("/api/tasks/batch", json={
            "raw_input": "读论文", "tasks": [{"title": "读论文", "category": "科学研究"}],
        }).json()["tasks"][0]
        old = api.patch("/api/tasks/" + old["id"], json={"status": "已完成"}).json()
    old_file = tmp_path / "legacy.json"
    subprocess.run([sys.executable, str(ROOT / "scripts/export_sqlite.py"),
                    server.env["DATABASE_PATH"], str(old_file)], check=True)
    page = browser.new_page()
    try:
        page.goto(static_site)
        page.get_by_role("button", name="操作历史").click()
        picker = page.get_by_label("选择任务备份")
        picker.set_input_files(old_file)
        expect(page.get_by_text("已导入 1 项任务", exact=False)).to_be_visible()
        picker.set_input_files(old_file)
        expect(page.get_by_text("跳过 1 项已有任务", exact=False)).to_be_visible()
        with page.expect_download() as download:
            page.get_by_role("button", name="导出备份").click()
        data = json.loads(Path(download.value.path()).read_text())
        assert len(data["tasks"]) == 1 and len(data["history"]) == 1
        saved = data["tasks"][0]
        assert saved["id"] == old["id"] and saved["raw_input"] == old["raw_input"]
        # SQLite stores offset +00:00; the HTTP serializer uses the equivalent Z.
        assert saved["completed_at"].replace("+00:00", "Z") == old["completed_at"]
        page.get_by_role("button", name="已完成", exact=True).click()
        expect(page.get_by_test_id("task-row")).to_have_count(1)
    finally:
        page.close()
