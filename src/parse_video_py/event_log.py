import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

MAX_EVENTS = 1000


def _data_dir() -> Path:
    return Path(os.getenv("PARSE_VIDEO_DATA_DIR", "data"))


def _events_path() -> Path:
    return _data_dir() / "events.jsonl"


_events: List[Dict] = []
_lock = threading.Lock()


def load() -> None:
    """重置内存列表并载入已持久化的事件（JSONL），损坏行跳过"""
    path = _events_path()
    with _lock:
        _events.clear()
        if not path.is_file():
            return
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        for line in lines[-MAX_EVENTS:]:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict):
                _events.append(entry)


def record(
    event_type: str, status: str, message: str, user: Optional[str] = None
) -> Dict:
    """记录一条系统事件：内存列表 + JSONL 追加持久化（写盘失败不影响业务）"""
    entry = {
        "t": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "status": status,
        "user": user or "",
        "message": message,
    }
    with _lock:
        _events.append(entry)
        if len(_events) > MAX_EVENTS:
            del _events[: len(_events) - MAX_EVENTS]
        path = _events_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass
    return entry


def list_events(limit: int = 200) -> List[Dict]:
    """按时间倒序返回最近的事件"""
    with _lock:
        return list(reversed(_events[-limit:]))
