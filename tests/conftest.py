"""在临时目录启动真实 HTTP 服务并用 Chromium 访问构建后的 Vue 页面。"""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from playwright.sync_api import sync_playwright

from pages_build import build_pages, serve_pages

ROOT = Path(__file__).resolve().parents[1]


class LocalServer:
    def __init__(self, directory):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.env = {
            **os.environ,
            "AI_MODE": "mock",
            "DEEPSEEK_API_KEY": "",
            "DATABASE_PATH": str(directory / "acceptance.sqlite3"),
            "APP_TIMEZONE": "Asia/Shanghai",
        }
        self.process = None

    def start(self):
        self.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host",
             "127.0.0.1", "--port", str(self.port), "--log-level", "warning"],
            cwd=ROOT / "backend",
            env=self.env,
        )
        for _ in range(100):
            if self.process.poll() is not None:
                raise RuntimeError("验收服务启动失败")
            try:
                with urlopen(self.url + "/api/health", timeout=1):
                    return
            except URLError:
                time.sleep(0.1)
        raise TimeoutError("等待本地 API 超时")

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    def restart(self):
        self.stop()
        self.start()


@pytest.fixture
def server(tmp_path):
    app = LocalServer(tmp_path)
    try:
        app.start()
        yield app
    finally:
        app.stop()


@pytest.fixture(scope="session")
def playwright_driver():
    with sync_playwright() as driver:
        yield driver


@pytest.fixture(scope="session")
def browser(playwright_driver):
    executable = os.environ.get("CHROME_PATH") or shutil.which("google-chrome")
    mac_chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if not executable and mac_chrome.is_file():
        executable = str(mac_chrome)
    instance = playwright_driver.chromium.launch(executable_path=executable)
    yield instance
    instance.close()


@pytest.fixture(scope="session")
def static_site(tmp_path_factory):
    root = tmp_path_factory.mktemp("static-pages")
    build_pages(root / "AI-Todo")
    with serve_pages(root) as url:
        yield url
