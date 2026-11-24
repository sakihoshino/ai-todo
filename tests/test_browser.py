"""使用桌面和移动视口，以正常页面入口验证完整任务流程。"""
import pytest
from playwright.sync_api import expect

PLACEHOLDER = "今天有什么想做的？直接告诉我就好。"


@pytest.mark.parametrize("mobile", [False, True], ids=["desktop", "mobile"])
def test_task_lifecycle(browser, server, mobile):
    context = browser.new_context(
        viewport={"width": 390 if mobile else 1440, "height": 844 if mobile else 1000},
        is_mobile=mobile, has_touch=mobile, locale="zh-CN",
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        page.goto(server.url)
        composer = page.get_by_placeholder(PLACEHOLDER)
        parse = page.get_by_role("button", name="AI 整理任务", exact=True)
        composer.fill("明天写数据库作业，读论文")
        parse.click()
        titles = page.get_by_label("预览任务名称", exact=True)
        expect(titles).to_have_count(2)
        page.get_by_label("移除预览任务", exact=True).last.click()
        titles.first.fill("整理课程数据库笔记")
        expect(page.get_by_test_id("task-row")).to_have_count(0)
        page.get_by_role("button", name="确认保存").click()
        row = page.get_by_test_id("task-row").filter(has_text="整理课程数据库笔记")
        expect(row).to_be_visible()
        page.reload()
        expect(row).to_be_visible()
        row.get_by_label("标记完成", exact=True).click()
        if mobile:
            page.get_by_role("button", name="打开导航").click()
        page.get_by_role("navigation").get_by_role("button", name="已完成").first.click()
        expect(row).to_be_visible()
        row.get_by_label("恢复待办", exact=True).click()
        expect(row).to_have_count(0)
        if mobile:
            page.get_by_role("button", name="打开导航").click()
        page.get_by_role("navigation").get_by_role("button", name="全部任务").first.click()
        row.get_by_label("编辑任务", exact=True).click()
        page.get_by_label("任务名称", exact=True).fill("提交课程笔记")
        page.get_by_role("button", name="保存修改").click()
        updated = page.get_by_test_id("task-row").filter(has_text="提交课程笔记")
        expect(updated).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        updated.get_by_label("删除任务", exact=True).click()
        page.get_by_role("button", name="确认删除").click()
        expect(updated).to_have_count(0)
        assert server_row_count(page, server) == 0
        assert not errors
    finally:
        context.close()


def server_row_count(page, server):
    response = page.request.get(server.url + "/api/tasks")
    assert response.ok
    return len(response.json()["tasks"])


def test_failure_retains_input_without_saving(browser, server):
    server.stop()
    server.env["AI_MODE"] = "deepseek"
    server.start()
    page = browser.new_page()
    try:
        page.goto(server.url)
        composer = page.get_by_placeholder(PLACEHOLDER)
        composer.fill("明天写数据库作业")
        expect(page.get_by_text("API Key", exact=False).first).to_be_visible()
        parse = page.get_by_role("button", name="AI 整理任务", exact=True)
        if parse.is_enabled():
            with page.expect_response(lambda r: r.url.endswith("/api/tasks/parse")) as reply:
                parse.click()
            assert reply.value.status >= 400
        expect(composer).to_have_value("明天写数据库作业")
        expect(page.get_by_label("预览任务名称", exact=True)).to_have_count(0)
        assert server_row_count(page, server) == 0
    finally:
        page.close()


def test_upstream_error_is_shown_without_creating_tasks(browser, server):
    page = browser.new_page()
    try:
        page.route("**/api/tasks/parse", lambda route: route.fulfill(
            status=402,
            content_type="application/json",
            json={"detail": "DeepSeek 账户余额不足，请充值后重新整理。"},
        ))
        page.goto(server.url)
        composer = page.get_by_placeholder(PLACEHOLDER)
        composer.fill("明天写数据库作业")
        page.get_by_role("button", name="AI 整理任务", exact=True).click()
        expect(page.get_by_text("DeepSeek 账户余额不足，请充值后重新整理。")).to_be_visible()
        expect(composer).to_have_value("明天写数据库作业")
        expect(page.get_by_label("预览任务名称", exact=True)).to_have_count(0)
        assert server_row_count(page, server) == 0
    finally:
        page.close()


def test_views_filters_and_sorting(browser, server):
    from datetime import date, timedelta

    page = browser.new_page()
    try:
        today = date.fromisoformat(page.request.get(server.url + "/api/health").json()["today"])
        tomorrow = today + timedelta(days=1)
        rows = [
            {"title": "复习课程", "category": "课程学习", "due_date": str(today)},
            {"title": "阅读论文", "category": "科学研究", "due_date": str(tomorrow)},
            {"title": "整理资料", "category": "科学研究"},
        ]
        saved = page.request.post(server.url + "/api/tasks/batch", data={
            "raw_input": "复习课程，阅读论文，整理资料", "tasks": rows
        }).json()["tasks"]
        assert page.request.patch(server.url + "/api/tasks/" + saved[2]["id"],
                                  data={"status": "已完成"}).ok
        page.goto(server.url)
        nav = page.get_by_role("navigation")
        titles = page.get_by_test_id("task-row").locator(".task-body strong")
        expect(titles).to_have_text(["复习课程", "阅读论文", "整理资料"])
        page.get_by_label("排序方式").select_option("due_desc")
        expect(titles).to_have_text(["阅读论文", "复习课程", "整理资料"])
        nav.get_by_role("button", name="今日任务").click()
        expect(titles).to_have_text(["复习课程"])
        nav.get_by_role("button", name="即将到期").click()
        expect(titles).to_have_text(["阅读论文"])
        nav.get_by_role("button", name="科学研究").click()
        expect(titles).to_have_text(["阅读论文", "整理资料"])
        page.get_by_label("按完成状态筛选").select_option("已完成")
        expect(titles).to_have_text(["整理资料"])
    finally:
        page.close()
