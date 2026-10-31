import json
import os
import secrets
from pathlib import Path
from typing import Dict, Optional, Tuple

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin123"

# 会话仅存在于进程内存，重启后失效（凭据文件持久化）
_sessions: Dict[str, str] = {}


def _data_dir() -> Path:
    return Path(os.getenv("PARSE_VIDEO_DATA_DIR", "data"))


def _credentials_path() -> Path:
    return _data_dir() / "credentials.json"


def load_credentials() -> Tuple[str, str]:
    path = _credentials_path()
    if path.is_file():
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("username") and data.get("password"):
                return str(data["username"]), str(data["password"])
        except (OSError, json.JSONDecodeError):
            pass

    env_user = os.getenv("PARSE_VIDEO_USERNAME")
    env_pass = os.getenv("PARSE_VIDEO_PASSWORD")
    if env_user and env_pass:
        return env_user, env_pass

    return DEFAULT_USERNAME, DEFAULT_PASSWORD


def save_credentials(username: str, password: str) -> None:
    path = _credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"username": username, "password": password}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def verify_credentials(username: str, password: str) -> bool:
    stored_username, stored_password = load_credentials()
    ok_user = secrets.compare_digest(str(username), stored_username)
    ok_pass = secrets.compare_digest(str(password), stored_password)
    return ok_user and ok_pass


def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = username
    return token


def get_session_user(token: str) -> Optional[str]:
    if not token:
        return None
    return _sessions.get(token)


def drop_session(token: str) -> None:
    _sessions.pop(token, None)


def clear_sessions() -> None:
    _sessions.clear()
