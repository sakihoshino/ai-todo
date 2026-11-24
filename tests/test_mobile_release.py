"""在 WebKit/iPhone 与 Chromium/Pixel 触屏配置下检查布局、弹窗和离线重开。"""
import pytest
from playwright.sync_api import expect


@pytest.fixture(scope="module")
def webkit(playwright_driver):
    engine = playwright_driver.webkit.launch()
    yield engine
    engine.close()


@pytest.fixture(params=[("webkit", "iPhone 13"), ("browser", "Pixel 7")], ids=["iphone-webkit", "android-chrome"])
def phone(request, playwright_driver):
    engine_name, device_name = request.param
    engine = request.getfixturevalue(engine_name)
    context = engine.new_context(**playwright_driver.devices[device_name], locale="zh-CN")
    yield context
    context.close()


def assert_no_horizontal_scroll(page):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")


def assert_touch_target(button):
    box = button.bounding_box()
    assert box and box["width"] >= 44 and box["height"] >= 44


def test_touch_controls_keyboard_and_rotation(phone, static_site):
    page = phone.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(static_site)
    expect(page.get_by_text("清单还是空的")).to_be_visible()
    original = page.viewport_size
    nav = page.get_by_role("button", name="打开导航")
    add = page.get_by_role("button", name="新增任务", exact=True)
    assert_touch_target(nav)
    assert_touch_target(add)
    assert_touch_target(page.get_by_role("button", name="解析设置"))
    assert_no_horizontal_scroll(page)
    nav.tap()
    expect(page.get_by_role("button", name="课程学习", exact=True)).to_be_visible()
    page.get_by_role("button", name="课程学习", exact=True).tap()
    add.tap()
    title = page.get_by_label("任务名称", exact=True)
    title.fill("手机上编辑较长的待办 " + "A" * 95)
    expect(page.get_by_role("combobox", name="任务分类", exact=True)).to_have_value("课程学习")
    # A shortened viewport tests keyboard-constrained layout and scrolling.
    # Mobile OS keyboards and device cutouts require a separate real-device check.
    page.set_viewport_size({"width": 320, "height": 310})
    dialog = page.get_by_role("dialog", name="新增任务")
    expect(dialog).to_be_visible()
    dialog_box = dialog.bounding_box()
    assert dialog_box["height"] <= 310 and dialog_box["width"] <= 320
    details = page.get_by_label("补充说明")
    details.fill("移动端验收。" * 4)
    save = page.get_by_role("button", name="保存任务")
    save.scroll_into_view_if_needed()
    assert_touch_target(save)
    bounds = save.bounding_box()
    assert 0 <= bounds["y"] and bounds["y"] + bounds["height"] <= 311
    save.tap()
    row = page.get_by_test_id("task-row")
    expect(row).to_be_visible()
    assert_no_horizontal_scroll(page)
    done = row.get_by_label("标记完成")
    assert_touch_target(done)
    assert_touch_target(row.get_by_label("编辑任务", exact=True))
    assert_touch_target(row.get_by_label("删除任务", exact=True))
    done.tap()
    expect(row.get_by_label("恢复待办")).to_be_visible()
    page.set_viewport_size({"width": original["height"], "height": original["width"]})
    assert_no_horizontal_scroll(page)
    nav.tap()
    page.get_by_role("button", name="操作历史").tap()
    expect(page.get_by_text("完成", exact=True)).to_be_visible()
    assert_touch_target(page.get_by_role("button", name="导入任务"))
    assert_touch_target(page.get_by_role("button", name="导出备份"))
    assert errors == []


def test_phone_offline_page_reopen(phone, static_site):
    page = phone.new_page()
    page.goto(static_site)
    expect(page.get_by_text("清单还是空的")).to_be_visible()
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    page.reload()
    page.wait_for_function("Boolean(navigator.serviceWorker.controller)")
    page.get_by_role("button", name="新增任务", exact=True).tap()
    page.get_by_label("任务名称", exact=True).fill("离线查看移动端任务")
    page.get_by_role("button", name="保存任务").tap()
    row = page.get_by_test_id("task-row")
    expect(row).to_contain_text("离线查看移动端任务")
    page.close()
    phone.set_offline(True)
    reopened = phone.new_page()
    reopened.goto(static_site)
    expect(reopened.get_by_test_id("task-row")).to_contain_text("离线查看移动端任务")
    expect(reopened.get_by_text("离线模式", exact=True)).to_be_visible()
    assert_no_horizontal_scroll(reopened)
