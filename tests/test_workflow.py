"""跨越解析、确认和真实进程重启的 HTTP 验收测试。"""
from datetime import date, timedelta

import httpx

SAMPLE = "明天写完数据库作业，周五之前提交社区实践周记，今天晚上背50个六级单词，还有空的时候看一下学长发来的论文。"


def test_confirmed_sample_survives_restart(server):
    with httpx.Client(base_url=server.url, trust_env=False) as api:
        today = date.fromisoformat(api.get("/api/health").json()["today"])
        result = api.post("/api/tasks/parse", json={"raw_input": SAMPLE})
        result.raise_for_status()
        drafts = result.json()["tasks"]
        assert len(drafts) == 4
        assert api.get("/api/tasks").json()["tasks"] == []
        homework, journal, english, paper = drafts
        assert homework["due_date"] == (today + timedelta(days=1)).isoformat()
        assert date.fromisoformat(journal["due_date"]).weekday() == 4
        assert english["due_date"] == today.isoformat()
        assert english["due_time"] is None
        assert paper["due_date"] is None
        homework["title"] = "提交数据库课程作业终稿"
        result = api.post("/api/tasks/batch", json={"raw_input": SAMPLE, "tasks": drafts})
        result.raise_for_status()
        records = result.json()["tasks"]
        assert all(task["raw_input"] == SAMPLE for task in records)
        saved_id = next(item["id"] for item in records if item["title"] == homework["title"])

    server.restart()
    with httpx.Client(base_url=server.url, trust_env=False) as api:
        assert len(api.get("/api/tasks").json()["tasks"]) == 4
        task = api.get(f"/api/tasks/{saved_id}").json()
        assert task["title"] == homework["title"]
        assert task["due_date"] == homework["due_date"]
