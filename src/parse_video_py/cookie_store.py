import json
import os
from pathlib import Path
from typing import Dict


def _data_dir() -> Path:
    return Path(os.getenv("PARSE_VIDEO_DATA_DIR", "data"))


def _cookies_path() -> Path:
    return _data_dir() / "platform_cookies.json"


def _load_cookies() -> Dict[str, str]:
    path = _cookies_path()
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cookies(cookies: Dict[str, str]) -> None:
    path = _cookies_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")


def get_cookie(source: str) -> str:
    return _load_cookies().get(source, "")


def list_cookies() -> Dict[str, str]:
    return _load_cookies()


def set_cookie(source: str, value: str) -> None:
    cookies = _load_cookies()
    cookies[source] = value
    _save_cookies(cookies)


def delete_cookie(source: str) -> bool:
    cookies = _load_cookies()
    if source not in cookies:
        return False
    del cookies[source]
    _save_cookies(cookies)
    return True
