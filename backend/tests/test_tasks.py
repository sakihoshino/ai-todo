import sqlite3
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def save(client, tasks, **kwargs):
    return client.post("/api/tasks/batch", json={"raw_input": "原始输入", "tasks": tasks}, **kwargs)


def test_edited_draft_save_and_lifecycle(client):
    parsed = client.post("/api/tasks/parse", json={"raw_input": "明天写完数据库作业"})
    assert parsed.status_code == 200
    assert len(parsed.json()["tasks"]) == 1
    assert client.get("/api/tasks").json()["tasks"] == []
    draft = parsed.json()["tasks"][0]
    draft.update(title="完成数据库作业第三章", due_date=None, due_time=None)
    created = client.post("/api/tasks/batch", json={
        "raw_input": "明天写完数据库作业", "tasks": [draft],
    })
    assert created.status_code == 201
    task = created.json()["tasks"][0]
    url = "/api/tasks/" + task["id"]
    assert task["title"] == "完成数据库作业第三章"
    assert task["raw_input"] == "明天写完数据库作业" and task["due_date"] is None
    assert task["created_at"] == task["updated_at"] and task["completed_at"] is None
    assert client.get(url).json() == task

    done = client.patch(url, json={"status": "已完成"}).json()
    assert done["completed_at"] and done["updated_at"] >= task["updated_at"]
    assert client.patch(url, json={"status": "已完成"}).json() == done
    assert client.patch(url, json={"status": "待完成"}).json()["completed_at"] is None
    edited = client.patch(url, json={"due_date": "2030-12-01", "due_time": "09:30", "description": "带好资料"})
    assert edited.json()["description"] == "带好资料"
    assert client.patch(url, json={"due_time": None}).json()["due_time"] is None
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404 and client.delete(url).status_code == 404


def test_persistent_database_across_app_instances(settings):
    with TestClient(create_app(settings)) as first:
        task = save(first, [{"title": "整理笔记"}]).json()["tasks"][0]
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get("/api/tasks").json()["tasks"] == [task]


def test_batch_idempotency(client):
    headers = {"Idempotency-Key": str(uuid4())}
    tasks = [{"title": "阅读论文"}, {"title": "修改图表"}]
    original = save(client, tasks, headers=headers)
    retry = save(client, tasks, headers=headers)
    assert original.status_code == 201
    assert retry.json() == original.json()
    assert len(client.get("/api/tasks").json()["tasks"]) == 2
    assert save(client, [{"title": "另一批任务"}], headers=headers).status_code == 409


@pytest.mark.parametrize("bad", [
    {"title": " "}, {"title": "修改作业", "priority": "超级高"},
    {"title": "修改作业", "due_date": "2025-02-29"}, {"title": "任务", "due_time": "24:00"},
    {"title": "任务", "status": "已完成"}, {"title": "任务", "category": "乱写的分类"},
])
def test_no_partial_batch_on_validation_error(client, bad):
    assert save(client, [{"title": "有效任务"}, bad]).status_code == 422
    assert client.get("/api/tasks").json() == {"tasks": []}


def test_database_errors_are_atomic_and_redacted(client, settings):
    # Force a failure partway through a valid batch, after the first INSERT.
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute("""
            CREATE TRIGGER fail_second BEFORE INSERT ON tasks WHEN NEW.title='第二项'
            BEGIN SELECT RAISE(ABORT, 'private diagnostic'); END;
        """)
    result = save(client, [{"title": "第一项"}, {"title": "第二项"}])
    assert result.status_code == 503 and "private diagnostic" not in result.text
    assert client.get("/api/tasks").json()["tasks"] == []


@pytest.mark.parametrize("patch", [{"title": None}, {"id": "external"}, {}, {"raw_input": "new"}])
def test_patch_rejects_invalid_changes(client, patch):
    task = save(client, [{"title": "买菜"}]).json()["tasks"][0]
    url = "/api/tasks/" + task["id"]
    assert client.patch(url, json=patch).status_code == 422
    assert client.get(url).json() == task


def test_sort_filters_and_health(client):
    health = client.get("/api/health").json()
    assert health["timezone"] == "Asia/Shanghai" and health["configured"] is False
    assert health["mode"] == "mock" and health["status"] == "ok"
    today = date.fromisoformat(health["today"])
    tasks = [
        {"title": "远期", "due_date": (today + timedelta(days=8)).isoformat()},
        {"title": "今天", "due_date": today.isoformat(), "due_time": "23:30"},
        {"title": "历史", "due_date": (today - timedelta(days=1)).isoformat()},
        {"title": "下周", "due_date": (today + timedelta(days=7)).isoformat()},
        {"title": "未定", "category": "日常生活"},
    ]
    saved = save(client, tasks).json()["tasks"]
    client.patch("/api/tasks/" + saved[2]["id"], json={"status": "已完成"})

    def titles(**params):
        return [task["title"] for task in client.get("/api/tasks", params=params).json()["tasks"]]
    assert titles(view="today") == ["今天"]
    assert titles(view="upcoming") == ["下周"]
    assert titles(view="completed") == titles(status="已完成") == ["历史"]
    assert titles(category="日常生活", status="待完成") == ["未定"]
    assert titles(sort="due_asc") == ["历史", "今天", "下周", "远期", "未定"]
    assert titles(sort="due_desc") == ["远期", "下周", "今天", "历史", "未定"]


def test_reject_cross_origin_mutation(client):
    result = save(client, [{"title": "未授权"}], headers={"Origin": "https://unrelated.example"})
    assert result.status_code == 403
    assert client.get("/api/tasks").json() == {"tasks": []}
