"""Read local configuration once, without loading secrets into process-wide state."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parents[1]
Mode = Literal["mock", "deepseek"]


@dataclass(frozen=True)
class Settings:
    mode: Mode = "mock"
    api_key: str = field(default="", repr=False)
    model: str = "deepseek-flash"
    timezone: str = "Asia/Shanghai"
    database_path: Path = BACKEND_DIR / "data" / "tasks.sqlite3"

    @classmethod
    def from_env(cls) -> "Settings":
        env = {**dotenv_values(BACKEND_DIR / ".env", interpolate=False), **os.environ}
        mode = env.get("AI_MODE", "mock")
        if mode not in ("mock", "deepseek"):
            raise ValueError("AI_MODE 必须为 mock 或 deepseek")
        timezone = env.get("APP_TIMEZONE") or "Asia/Shanghai"
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("APP_TIMEZONE 必须是有效的 IANA 时区名称") from None
        path = Path(env.get("DATABASE_PATH") or "data/tasks.sqlite3").expanduser()
        return cls(
            mode=mode,
            api_key=(env.get("DEEPSEEK_API_KEY") or "").strip(),
            model=env.get("DEEPSEEK_MODEL") or "deepseek-flash",
            timezone=timezone,
            database_path=BACKEND_DIR / path,
        )
