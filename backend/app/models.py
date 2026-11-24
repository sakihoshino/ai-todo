"""Public API contracts. Dates are local calendar values; audit times include UTC."""
from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator,
)

from .config import Mode

Category = Literal["课程学习", "科学研究", "学生工作", "社会实践", "英语学习", "竞赛活动", "日常生活", "其他"]
Priority = Literal["高", "中", "低"]
Status = Literal["待完成", "已完成"]
View = Literal["all", "today", "upcoming", "completed"]
Sort = Literal["due_asc", "due_desc", "created_desc"]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


def valid_date(value: str) -> str:
    date.fromisoformat(value)
    return value


def nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("请输入任务内容")
    return value


DueDate = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"), AfterValidator(valid_date)]
DueTime = Annotated[str, StringConstraints(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")]
RawInput = Annotated[str, StringConstraints(min_length=1, max_length=4000), AfterValidator(nonblank)]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskDraft(Schema):
    title: Title
    description: Description = ""
    category: Category = "其他"
    due_date: DueDate | None = None
    due_time: DueTime | None = None
    priority: Priority = "中"


class ParseRequest(Schema):
    raw_input: RawInput


class ParseResult(Schema):
    tasks: list[TaskDraft]
    mode: Mode


class BatchRequest(ParseRequest):
    tasks: list[TaskDraft] = Field(min_length=1, max_length=50)


class Task(TaskDraft):
    id: str
    status: Status
    raw_input: RawInput
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class TaskList(Schema):
    tasks: list[Task]


class TaskPatch(Schema):
    title: Title | None = None
    description: Description | None = None
    category: Category | None = None
    due_date: DueDate | None = None
    due_time: DueTime | None = None
    priority: Priority | None = None
    status: Status | None = None

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("请提供需要修改的字段")
        for name in self.model_fields_set - {"due_date", "due_time"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} 不能为空")
        return self
