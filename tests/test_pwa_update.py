"""Two independent production builds, one installed origin, and an offline relaunch."""
from urllib.parse import urljoin

from playwright.sync_api import expect

from pages_build import SUBPATH, build_pages, serve_pages


def test_update_keeps_tasks_and_history(browser, tmp_path):
    # Changing the asset path produces different HTML and Workbox precache revisions
    # without editing the source tree or hand-patching a generated service worker.
    first, second = tmp_path / "release-a", tmp_path / "release-b"
    build_pages(first, "--assetsDir", "assets-a")
    build_pages(second, "--assetsDir", "assets-b")
    assert (first / "sw.js").read_bytes() != (second / "sw.js").read_bytes()

    root = tmp_path / "pages"
    root.mkdir()
    path = root / SUBPATH.strip("/")
    path.symlink_to(first, target_is_directory=True)
    (root / "observer.html").write_text("<!doctype html><title>Lifecycle observer</title>")
    context = browser.new_context()
    try:
        with serve_pages(root) as url:
            page = context.new_page()
            page.goto(url)
            assert page.evaluate("async () => (await navigator.serviceWorker.ready).scope") == url
            page.reload()
            assert page.evaluate("Boolean(navigator.serviceWorker.controller)")
            assert page.locator('script[type="module"]').get_attribute("src").startswith(SUBPATH + "assets-a/")
            page.get_by_role("button", name="新增任务", exact=True).click()
            page.get_by_label("任务名称", exact=True).fill("升级前保留的任务")
            page.get_by_role("button", name="保存任务", exact=True).click()
            row = page.get_by_test_id("task-row")
            expect(row).to_have_count(1)
            row.get_by_label("标记完成").click()
            expect(row.get_by_label("恢复待办")).to_be_visible()
            before = context.storage_state(indexed_db=True)["origins"]
            tasks_db = next(db for db in before[0]["indexedDB"] if db["name"] == "AI-Todo")
            stores = {store["name"]: store["records"] for store in tasks_db["stores"]}
            assert len(stores["tasks"]) == 1 and len(stores["history"]) == 2

            # An observer outside the app scope stays online when the last PWA window closes.
            observer = context.new_page()
            observer.goto(urljoin(url, "../observer.html"))
            assert not observer.evaluate("Boolean(navigator.serviceWorker.controller)")
            observer.evaluate("""async path => {
                window.reg = await navigator.serviceWorker.getRegistration(path)
                window.firstWorker = window.reg.active
            }""", url)
            deploy = root / "next"
            deploy.symlink_to(second, target_is_directory=True)
            deploy.replace(path)
            observer.evaluate("async () => { await window.reg.update() }")
            observer.wait_for_function("window.reg.waiting && window.reg.waiting.state === 'installed'")
            assert observer.evaluate("window.firstWorker === window.reg.active")
            page.close()
            observer.wait_for_function("""window.reg.active !== window.firstWorker &&
                window.reg.active?.state === 'activated' && !window.reg.waiting""")

            context.set_offline(True)
            upgraded = context.new_page()
            upgraded.goto(url)
            assert upgraded.evaluate("Boolean(navigator.serviceWorker.controller)")
            assert upgraded.locator('script[type="module"]').get_attribute("src").startswith(SUBPATH + "assets-b/")
            saved = upgraded.get_by_test_id("task-row")
            expect(saved).to_contain_text("升级前保留的任务")
            expect(saved.get_by_label("恢复待办")).to_be_visible()
            assert context.storage_state(indexed_db=True)["origins"] == before
    finally:
        context.close()
