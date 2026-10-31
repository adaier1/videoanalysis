import json
import os
import secrets
from pathlib import Path
from typing import Dict, Optional

DEFAULT_OWNER = "default"


def _data_dir() -> Path:
    return Path(os.getenv("PARSE_VIDEO_DATA_DIR", "data"))


def _keys_path() -> Path:
    return _data_dir() / "api_keys.json"


def generate_key() -> str:
    return secrets.token_urlsafe(24)


def _load_keys() -> Dict[str, str]:
    path = _keys_path()
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_keys(keys: Dict[str, str]) -> None:
    path = _keys_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(keys, ensure_ascii=False, indent=2), encoding="utf-8")


def get_or_create_key(owner: str) -> str:
    keys = _load_keys()
    if owner not in keys:
        keys[owner] = generate_key()
        _save_keys(keys)
    return keys[owner]


def reset_key(owner: str) -> str:
    keys = _load_keys()
    keys[owner] = generate_key()
    _save_keys(keys)
    return keys[owner]


def find_owner(key: str) -> Optional[str]:
    if not key:
        return None
    keys = _load_keys()
    for owner, stored in keys.items():
        if secrets.compare_digest(str(stored), str(key)):
            return owner
    return None
