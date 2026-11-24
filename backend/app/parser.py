"""Parse previews only. This module has no database dependency."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Self

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .config import Settings
from .mock_parser import parse_mock
from .models import TaskDraft


PROMPT = (Path(__file__).parent / "prompts" / "task_parser.txt").read_text(encoding="utf-8")
ENDPOINT = "https://api.deepseek.com/chat/completions"
UPSTREAM_ERRORS = {
    400: (502, "DeepSeek 拒绝了请求，请检查后端配置的模型名称。"),
    401: (503, "DeepSeek 鉴权失败，请检查后端 .env 中的 API Key。"),
    402: (402, "DeepSeek 账户余额不足，请充值后重新整理。"),
    403: (503, "当前 API Key 无权使用此服务，请检查账户权限。"),
    408: (504, "DeepSeek 响应超时，请稍后重试。"),
    422: (502, "DeepSeek 不支持当前请求参数，请检查模型配置。"),
    429: (429, "DeepSeek 请求过于频繁，请稍后重试。"),
    504: (504, "DeepSeek 响应超时，请稍后重试。"),
}


class ParsedTasks(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tasks: list[TaskDraft] = Field(max_length=50)

    @model_validator(mode="after")
    def require_all_fields(self) -> Self:
        required_fields = set(TaskDraft.model_fields)
        if any(task.model_fields_set != required_fields for task in self.tasks):
            raise ValueError("解析结果缺少任务字段")
        return self


async def parse_tasks(
    raw_input: str,
    settings: Settings,
    now: datetime,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[TaskDraft]:
    if settings.mode == "mock":
        try:
            return ParsedTasks(tasks=parse_mock(raw_input, now.date())).tasks
        except ValidationError:
            raise HTTPException(422, "这段内容生成的任务过多或过长，请分段整理。") from None
    if not settings.api_key:
        raise HTTPException(503, "请在后端 .env 配置 DEEPSEEK_API_KEY，或切换为 Mock 模式后重启。")

    if not settings.api_key.isascii() or not settings.api_key.isprintable():
        raise HTTPException(503, "后端 .env 中的 DEEPSEEK_API_KEY 格式有误，请检查后重启。")

    weekday = "一二三四五六日"[now.weekday()]
    context = f"本地时间 {now.isoformat(timespec='seconds')}，星期{weekday}，时区 {settings.timezone}。"
    body = {
        "model": settings.model,
        "messages": [
            {"role": "system", "content": f"{PROMPT}\n{context}"},
            {"role": "user", "content": raw_input},
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "stream": False,
        "max_tokens": 8192,
    }
    try:
        # Bound total duration as well as individual network operations.
        async with asyncio.timeout(60), httpx.AsyncClient(transport=transport, timeout=55.0) as client:
            response = await client.post(
                ENDPOINT, json=body, headers={"Authorization": f"Bearer {settings.api_key}"}
            )
    except (TimeoutError, httpx.TimeoutException):
        raise HTTPException(504, "DeepSeek 响应超时，请稍后重试。") from None
    except httpx.RequestError:
        raise HTTPException(502, "无法连接 DeepSeek，请检查网络后重试。") from None

    if not response.is_success:
        status, message = UPSTREAM_ERRORS.get(response.status_code, (502, "DeepSeek 服务暂不可用，请稍后重试。"))
        raise HTTPException(status, message)
    try:
        choice = response.json()["choices"][0]
        if choice["finish_reason"] != "stop":
            raise HTTPException(502, "DeepSeek 未完整输出，请缩短输入后重试。")
        content = choice["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise HTTPException(502, "DeepSeek 返回空内容，请重新整理。")
        return ParsedTasks.model_validate_json(content).tasks
    except (ValueError, IndexError, KeyError, TypeError):
        # Upstream errors may echo the input or credentials. Return only a local message.
        raise HTTPException(502, "DeepSeek 返回的 JSON 或任务字段无效，请重新整理。") from None
