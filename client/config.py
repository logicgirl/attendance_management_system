"""Where the API server lives.

Lookup order: ATTENDEASE_API_URL environment variable, the user's saved setting
(%APPDATA%/AttendEase/config.json), a config.json shipped next to the program,
then the local development server.
"""

import json
import os
import sys
from pathlib import Path

DEFAULT_API_URL = "http://127.0.0.1:8000"


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _user_config_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "AttendEase" / "config.json"


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_api_url() -> str:
    if url := os.environ.get("ATTENDEASE_API_URL"):
        return url
    for path in (_user_config_path(), _app_dir() / "config.json"):
        if url := _read(path).get("api_url"):
            return url
    return DEFAULT_API_URL


def save_api_url(url: str) -> None:
    path = _user_config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = _read(path) | {"api_url": url}
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass  # Not being able to remember the server is not worth interrupting the user
