"""SQLite operations with one short-lived connection per read or write transaction."""
import hashlib
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from .models import BatchRequest, Category, Sort, Status, TaskPatch, View

COLUMNS = """id, title, description, category, due_date, due_time, priority,
             status, raw_input, created_at, updated_at, completed_at"""


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    due_date TEXT,
                    due_time TEXT,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('待完成','已完成')),
                    raw_input TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    batch_key TEXT
                );
                CREATE INDEX IF NOT EXISTS tasks_due ON tasks(due_date, due_time);
                CREATE INDEX IF NOT EXISTS tasks_batch ON tasks(batch_key);
                CREATE TABLE IF NOT EXISTS batches (
                    key TEXT PRIMARY KEY,
                    digest TEXT NOT NULL
                );
            """)

    def check(self) -> None:
        with self.connect() as db:
            db.execute("SELECT id FROM tasks LIMIT 1").fetchone()

    def save_batch(self, batch: BatchRequest, key: str | None) -> list[dict]:
        with self.connect(write=True) as db:
            if key:
                digest = hashlib.sha256(batch.model_dump_json().encode()).hexdigest()
                previous = db.execute("SELECT digest FROM batches WHERE key=?", (key,)).fetchone()
                if previous:
                    if previous["digest"] != digest:
                        raise HTTPException(409, "这次保存的内容已变更，请重新确认")
                    return [dict(row) for row in db.execute(
                        f"SELECT {COLUMNS} FROM tasks WHERE batch_key=? ORDER BY rowid", (key,)
                    )]
                db.execute("INSERT INTO batches VALUES (?,?)", (key, digest))

            now = datetime.now(UTC).isoformat()
            saved = []
            for task in batch.tasks:
                record = {
                    **task.model_dump(), "id": str(uuid4()), "status": "待完成",
                    "raw_input": batch.raw_input, "created_at": now, "updated_at": now,
                    "completed_at": None,
                }
                db.execute(
                    f"INSERT INTO tasks ({COLUMNS}, batch_key) VALUES "
                    "(:id,:title,:description,:category,:due_date,:due_time,:priority,"
                    ":status,:raw_input,:created_at,:updated_at,:completed_at,:batch_key)",
                    {**record, "batch_key": key},
                )
                saved.append(record)
            return saved

    def list_tasks(self, category: Category | None, status: Status | None,
                   view: View, sort: Sort, today: date) -> list[dict]:
        clauses, args = [], []
        if category:
            clauses.append("category=?")
            args.append(category)
        if status:
            clauses.append("status=?")
            args.append(status)
        if view == "today":
            clauses.append("status='待完成' AND due_date=?")
            args.append(today.isoformat())
        elif view == "upcoming":
            clauses.append("status='待完成' AND due_date>? AND due_date<=?")
            args.extend([today.isoformat(), (today + timedelta(days=7)).isoformat()])
        elif view == "completed":
            clauses.append("status='已完成'")
        order = {
            "due_asc": "due_date IS NULL, due_date ASC, due_time IS NULL, due_time ASC",
            "due_desc": "due_date IS NULL, due_date DESC, due_time IS NULL, due_time DESC",
            "created_desc": "created_at DESC",
        }[sort]
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                f"SELECT {COLUMNS} FROM tasks{where} ORDER BY {order}, rowid DESC", args
            )]

    @staticmethod
    def _find(db: sqlite3.Connection, task_id: str) -> dict:
        row = db.execute(f"SELECT {COLUMNS} FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "找不到这项任务")
        return dict(row)

    def get(self, task_id: str) -> dict:
        with self.connect() as db:
            return self._find(db, task_id)

    def patch(self, task_id: str, patch: TaskPatch) -> dict:
        with self.connect(write=True) as db:
            task = self._find(db, task_id)
            changes = patch.model_dump(exclude_unset=True)
            now = datetime.now(UTC).isoformat()
            if "status" in changes and changes["status"] != task["status"]:
                changes["completed_at"] = now if changes["status"] == "已完成" else None
            if any(value != task[name] for name, value in changes.items()):
                changes["updated_at"] = now
                # Keys come only from TaskPatch fields and the two server-owned timestamps.
                assignments = ", ".join(f"{name}=?" for name in changes)
                db.execute(f"UPDATE tasks SET {assignments} WHERE id=?",
                           (*changes.values(), task_id))
            return {**task, **changes}

    def delete(self, task_id: str) -> None:
        with self.connect(write=True) as db:
            cursor = db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            if not cursor.rowcount:
                raise HTTPException(404, "找不到这项任务")
