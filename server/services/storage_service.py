from __future__ import annotations

import os
import uuid
from pathlib import Path

from server.services.markdown_service import sanitize_filename


class StorageError(ValueError):
    pass


class StorageService:
    def __init__(self, root: str | Path):
        if not str(root).strip():
            raise StorageError("请先选择 Markdown 保存文件夹")
        self.root = Path(root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)
        self.root = self.root.resolve()

    def save_markdown(self, subdir: str, filename: str, content: str) -> Path:
        folder = self._safe_folder(subdir)
        folder.mkdir(parents=True, exist_ok=True)
        safe_name = sanitize_filename(filename)
        target = folder / f"{safe_name}.md"
        counter = 2
        while target.exists():
            target = folder / f"{safe_name} ({counter}).md"
            counter += 1

        resolved_target = target.resolve(strict=False)
        if not resolved_target.is_relative_to(self.root):
            raise StorageError("保存路径超出了已选择的文件夹")

        temp_path = folder / f".{safe_name}.{uuid.uuid4().hex}.tmp"
        try:
            temp_path.write_text(content, encoding="utf-8")
            os.replace(temp_path, target)
        except OSError as exc:
            temp_path.unlink(missing_ok=True)
            raise StorageError(f"无法保存 Markdown：{exc}") from exc
        return target

    def _safe_folder(self, subdir: str) -> Path:
        relative = Path(subdir.strip() or ".")
        if relative.is_absolute() or ".." in relative.parts:
            raise StorageError("子目录必须位于已选择的保存文件夹内")
        folder = (self.root / relative).resolve(strict=False)
        if not folder.is_relative_to(self.root):
            raise StorageError("子目录必须位于已选择的保存文件夹内")
        return folder
