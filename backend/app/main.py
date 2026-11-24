import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import BACKEND_DIR, Settings
from .database import Database
from .models import (
    BatchRequest, Category, ParseRequest, ParseResult, Sort, Status, Task, TaskList,
    TaskPatch, View,
)
from .parser import parse_tasks


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    db = Database(settings.database_path)
    timezone = ZoneInfo(settings.timezone)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        db.initialize()
        yield

    app = FastAPI(title="AI-Todo", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def require_local_origin(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.method in {"POST", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "请从当前工作区页面操作"}, status_code=403)
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(sqlite3.Error)
    async def database_error(request: Request, exc: sqlite3.Error):
        return JSONResponse({"detail": "无法访问本地任务数据库，请检查磁盘空间和文件权限后重试"}, status_code=503)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        # Echo field names only; raw inputs may contain private notes.
        first = exc.errors()[0]
        path = ".".join(str(item) for item in first["loc"][1:])
        detail = f"请检查字段 {path} 的内容或格式" if path else "请求内容格式有误"
        return JSONResponse({"detail": detail}, status_code=422)

    @app.get("/api/health")
    def health():
        db.check()
        return {
            "status": "ok", "mode": settings.mode, "configured": bool(settings.api_key),
            "timezone": settings.timezone, "today": datetime.now(timezone).date().isoformat(),
        }

    @app.post("/api/tasks/parse", response_model=ParseResult)
    async def parse(body: ParseRequest):
        tasks = await parse_tasks(body.raw_input, settings, datetime.now(timezone))
        return ParseResult(tasks=tasks, mode=settings.mode)

    @app.post("/api/tasks/batch", response_model=TaskList, status_code=201)
    def batch(body: BatchRequest, idempotency_key: Annotated[UUID | None, Header()] = None):
        return {"tasks": db.save_batch(body, str(idempotency_key) if idempotency_key else None)}

    @app.get("/api/tasks", response_model=TaskList)
    def list_tasks(category: Category | None = None, status: Status | None = None,
                   view: View = "all", sort: Sort = "due_asc"):
        return {"tasks": db.list_tasks(category, status, view, sort, datetime.now(timezone).date())}

    @app.get("/api/tasks/{task_id}", response_model=Task)
    def get_task(task_id: str):
        return db.get(task_id)

    @app.patch("/api/tasks/{task_id}", response_model=Task)
    def update_task(task_id: str, body: TaskPatch):
        return db.patch(task_id, body)

    @app.delete("/api/tasks/{task_id}", status_code=204)
    def delete_task(task_id: str):
        db.delete(task_id)
        return Response(status_code=204)

    dist = BACKEND_DIR.parent / "frontend" / "dist"
    if (dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
