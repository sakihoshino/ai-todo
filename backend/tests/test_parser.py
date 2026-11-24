"""Exercise the HTTP contract with a local transport. No requests incur API fees."""
import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi import HTTPException

from app.config import Settings
from app.parser import parse_tasks


NOW = datetime(2026, 11, 28, 23, 45, tzinfo=ZoneInfo("Asia/Shanghai"))  # Saturday
SAMPLE = "明天写完数据库作业，周五之前提交社区实践周记，今天晚上背50个六级单词，还有空的时候看一下学长发来的论文。"
DRAFT = dict(title="检查教案", description="", category="课程学习", due_date=None, due_time=None, priority="中")
REAL = Settings(mode="deepseek", api_key="test-placeholder", model="custom-model")


def run_mock(text):
    return asyncio.run(parse_tasks(text, Settings(), NOW))


def run_live(handler, settings=REAL):
    transport = httpx.MockTransport(handler)
    return asyncio.run(parse_tasks("检查教案", settings, NOW, transport=transport))


def completion(content, reason="stop"):
    return httpx.Response(200, json={"choices": [{"finish_reason": reason, "message": {"content": content}}]})


def test_mock_sample():
    tasks = run_mock(SAMPLE)
    assert [t.title for t in tasks] == ["写完数据库作业", "提交社区实践周记", "背50个六级单词", "看一下学长发来的论文"]
    assert [t.category for t in tasks] == ["课程学习", "社会实践", "英语学习", "科学研究"]
    assert [t.due_date for t in tasks] == ["2026-11-29", "2026-12-04", "2026-11-28", None]
    assert all(t.priority == "中" and t.due_time is None for t in tasks)


@pytest.mark.parametrize(("text", "day", "clock", "priority"), [
    ("今天买牛奶", "2026-11-28", None, "中"),
    ("后天写作业", "2026-11-30", None, "中"),
    ("本周五写论文", "2026-11-27", None, "中"),
    ("下周一下午三点半交作业", "2026-11-30", "15:30", "中"),
    ("明晚八点开会", "2026-11-29", "20:00", "中"),
    ("低优先级：整理文件", None, None, "低"),
    ("高优先级：18:15写总结", None, "18:15", "高"),
    ("2026年12月5日上午十点背单词", "2026-12-05", "10:00", "中"),
])
def test_mock_single_deadline(text, day, clock, priority):
    task, = run_mock(text)
    assert (task.due_date, task.due_time, task.priority) == (day, clock, priority)


@pytest.mark.parametrize("text", ["今天天气很好。", "今天心情很好", "不用买牛奶", "写作业了吗？", "你好！"])
def test_non_tasks(text):
    assert run_mock(text) == []


def test_live_request_and_validated_result():
    def handle(request):
        assert str(request.url) == "https://api.deepseek.com/chat/completions"
        assert request.headers["authorization"] == "Bearer test-placeholder"
        payload = json.loads(request.content)
        assert payload["model"] == "custom-model"
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["max_tokens"] > 0
        system, user = payload["messages"]
        assert all(hint in system["content"] for hint in ("Asia/Shanghai", "2026-11-28T23:45:00+08:00", "星期六", "JSON"))
        assert user == {"role": "user", "content": "检查教案"}
        return completion(json.dumps({"tasks": [DRAFT]}))

    task, = run_live(handle)
    assert task.model_dump() == DRAFT


def test_live_empty_list():
    assert run_live(lambda req: completion('{"tasks": []}')) == []


@pytest.mark.parametrize("response", [
    completion("   "), completion("not json"), completion('{"tasks":[]}', "length"),
    httpx.Response(200, content=b"broken"), httpx.Response(200, json={"choices": []}),
    completion('{"tasks": [{"title":"读论文"}]}'),
    completion(json.dumps({"tasks": [DRAFT, dict(DRAFT, priority="随便")]})),
    completion(json.dumps({"tasks": [dict(DRAFT, due_date="2026-02-30")]})),
    completion(json.dumps({"tasks": [dict(DRAFT, due_time="36:00")]})),
    completion(json.dumps({"tasks": [dict(DRAFT, status="已完成")]})),
])
def test_invalid_outputs_are_rejected_atomically(response):
    with pytest.raises(HTTPException) as err:
        run_live(lambda req: response)
    assert err.value.status_code == 502


@pytest.mark.parametrize(("upstream", "downstream", "message"), [
    (401, 503, "鉴权"), (402, 402, "余额"), (429, 429, "频繁"), (500, 502, "暂不"),
])
def test_upstream_errors_are_actionable_and_redacted(upstream, downstream, message):
    with pytest.raises(HTTPException) as err:
        run_live(lambda req: httpx.Response(upstream, text=REAL.api_key))
    assert err.value.status_code == downstream
    assert message in err.value.detail and REAL.api_key not in err.value.detail


@pytest.mark.parametrize(("error", "status"), [(httpx.ConnectError, 502), (httpx.ReadTimeout, 504)])
def test_network_errors(error, status):
    def fail(request):
        raise error("upstream failure", request=request)

    with pytest.raises(HTTPException) as err:
        run_live(fail)
    assert err.value.status_code == status


def test_missing_key_is_diagnosed_without_request():
    with pytest.raises(HTTPException) as err:
        run_live(lambda req: pytest.fail("unexpected network call"), Settings(mode="deepseek"))
    assert err.value.status_code == 503
    assert "DEEPSEEK_API_KEY" in err.value.detail


def test_rejected_upstream_response_creates_no_database_rows(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app

    async def insufficient_balance(self, request):
        return httpx.Response(402, text="private upstream diagnostic", request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", insufficient_balance)
    config = Settings(mode="deepseek", api_key=REAL.api_key, database_path=tmp_path / "failure.sqlite3")
    with TestClient(create_app(config)) as client:
        before = client.get("/api/tasks").json()
        result = client.post("/api/tasks/parse", json={"raw_input": "读论文"})
        assert result.status_code == 402
        assert result.json() == {"detail": "DeepSeek 账户余额不足，请充值后重新整理。"}
        assert client.get("/api/tasks").json() == before == {"tasks": []}
