from __future__ import annotations

import copy
import json
import os
import secrets
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "save_root": "",
    "page_subdir": "网页剪藏",
    "media_subdir": "视频转写",
    "whisper_model": "base",
    "ai": {
        "enabled": False,
        "provider": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
        "model": "",
        "api_key": "",
    },
}


class ConfigStore:
    """Small local JSON settings store with a private pairing token."""

    def __init__(self, path: str | Path | None = None):
        default_path = Path.home() / ".local-web-clipper" / "config.json"
        self.path = Path(path or os.getenv("LOCAL_WEB_CLIPPER_CONFIG", default_path))
        self._data = self._load()
        if not self._data.get("pairing_token"):
            self._data["pairing_token"] = secrets.token_urlsafe(32)
            self._save()

    @property
    def pairing_token(self) -> str:
        return str(self._data["pairing_token"])

    def get(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    def public_settings(self) -> dict[str, Any]:
        public = self.get()
        public.pop("pairing_token", None)
        api_key = public["ai"].pop("api_key", "")
        public["ai"]["has_api_key"] = bool(api_key)
        return public

    def update(self, changes: dict[str, Any]) -> dict[str, Any]:
        for key in ("save_root", "page_subdir", "media_subdir", "whisper_model"):
            if key in changes and isinstance(changes[key], str):
                self._data[key] = changes[key].strip()

        ai_changes = changes.get("ai")
        if isinstance(ai_changes, dict):
            for key in ("provider", "base_url", "model"):
                if key in ai_changes and isinstance(ai_changes[key], str):
                    self._data["ai"][key] = ai_changes[key].strip()
            if isinstance(ai_changes.get("enabled"), bool):
                self._data["ai"]["enabled"] = ai_changes["enabled"]
            if isinstance(ai_changes.get("api_key"), str) and ai_changes["api_key"]:
                self._data["ai"]["api_key"] = ai_changes["api_key"].strip()
            if ai_changes.get("clear_api_key") is True:
                self._data["ai"]["api_key"] = ""

        self._save()
        return self.public_settings()

    def _load(self) -> dict[str, Any]:
        data = copy.deepcopy(DEFAULT_SETTINGS)
        if self.path.exists():
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                stored = {}
            if isinstance(stored, dict):
                for key in ("save_root", "page_subdir", "media_subdir", "whisper_model", "pairing_token"):
                    if key in stored:
                        data[key] = stored[key]
                if isinstance(stored.get("ai"), dict):
                    data["ai"].update(stored["ai"])
        else:
            data["pairing_token"] = secrets.token_urlsafe(32)
            self._data = data
            self._save()
        return data

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(f".{self.path.name}.tmp")
        temp_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.chmod(temp_path, 0o600)
        temp_path.replace(self.path)
        os.chmod(self.path, 0o600)

