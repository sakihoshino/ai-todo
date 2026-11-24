"""将 V0.1 SQLite 快照导出为可在手机上导入的 UTF-8 任务文件。"""
import argparse
import json
import os
from pathlib import Path
import sqlite3


def export(database: Path, output: Path) -> int:
    uri = database.resolve(strict=True).as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("""
            SELECT id, title, description, category, due_date, due_time, priority,
                   status, raw_input, created_at, updated_at, completed_at
            FROM tasks ORDER BY created_at, id
        """)
        tasks = [dict(row) for row in rows]
    # 用户指定的新文件，不覆盖已有备份。
    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"tasks": tasks}, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return len(tasks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, help="现有 SQLite 文件或其备份")
    parser.add_argument("output", type=Path, help="新建 JSON 文件的位置")
    args = parser.parse_args()
    try:
        count = export(args.database, args.output)
    except (OSError, sqlite3.Error) as error:
        parser.exit(1, f"导出失败：{error}\n")
    print(f"已导出 {count} 项任务至 {args.output}")
