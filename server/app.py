from __future__ import annotations

import secrets
import subprocess
import sys
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import Flask, current_app, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from server.config_store import ConfigStore
from server.job_manager import JobManager
from server.services.ai_service import AIService, AIServiceError
from server.services.markdown_service import render_media_markdown, render_page_markdown
from server.services.media_service import MediaService
from server.services.storage_service import StorageError, StorageService


VERSION = "0.1.0"
MAX_JSON_BYTES = 8 * 1024 * 1024


class FolderSelectionError(RuntimeError):
    pass


def choose_folder_on_macos() -> str:
    if sys.platform != "darwin":
        raise FolderSelectionError("当前系统暂不支持弹出文件夹选择器，请手动填写路径")
    script = 'POSIX path of (choose folder with prompt "选择 Markdown 保存文件夹")'
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip()
        if "User canceled" in message or "-128" in message:
            raise FolderSelectionError("已取消选择文件夹")
        raise FolderSelectionError(message or "无法打开文件夹选择器")
    selected = result.stdout.strip()
    if not selected:
        raise FolderSelectionError("没有选择文件夹")
    return str(Path(selected).expanduser().resolve())


def create_app(
    config_path: str | Path | None = None,
    *,
    media_service: MediaService | None = None,
    ai_service: AIService | None = None,
    folder_selector: Callable[[], str] | None = None,
) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_JSON_BYTES
    store = ConfigStore(config_path)
    media = media_service or MediaService()
    ai = ai_service or AIService()
    select_folder = folder_selector or choose_folder_on_macos

    def organize_if_requested(
        text: str, note_type: str, requested: bool
    ) -> tuple[dict[str, Any] | None, str]:
        if not requested:
            return None, ""
        ai_settings = store.get()["ai"]
        if not ai_settings.get("enabled"):
            return None, "尚未在设置中启用 AI 整理，已保存完整原文"
        try:
            return ai.organize(text, ai_settings, note_type), ""
        except AIServiceError as exc:
            return None, f"AI 整理失败，已保存完整原文：{exc}"

    def process_media(payload: dict[str, Any], progress) -> dict[str, Any]:
        settings = store.get()
        result = media.transcribe(
            str(payload.get("url") or ""),
            settings.get("whisper_model", "base"),
            progress,
        )
        progress("organizing", "正在整理 Markdown")
        ai_result, warning = organize_if_requested(
            result.transcript, "media", bool(payload.get("ai_organize"))
        )
        metadata = {
            "title": result.title,
            "source": str(payload.get("url") or ""),
            "author": result.author,
            "published": "",
            "created": datetime.now().astimezone().isoformat(timespec="seconds"),
            "tags": ["视频转写"],
            "duration": result.duration,
            "transcription_method": result.method,
        }
        markdown = render_media_markdown(metadata, result.transcript, ai_result)
        path = StorageService(settings.get("save_root", "")).save_markdown(
            settings.get("media_subdir", "视频转写"), result.title, markdown
        )
        return {
            "path": str(path),
            "filename": path.name,
            "title": result.title,
            "method": result.method,
            "warning": warning,
        }

    jobs = JobManager(process_media)
    app.extensions["clipper_config_store"] = store
    app.extensions["clipper_job_manager"] = jobs

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin", "")
        if _is_extension_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, X-Local-Clipper-Key"
            )
            response.headers["Access-Control-Max-Age"] = "600"
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        return jsonify({"error": "请求内容过大，请缩短网页正文后重试"}), 413

    def require_token(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if request.method == "OPTIONS":
                return current_app.make_default_options_response()
            supplied = request.headers.get("X-Local-Clipper-Key", "")
            if not supplied or not secrets.compare_digest(supplied, store.pairing_token):
                return jsonify({"error": "本地服务配对信息无效，请重新连接"}), 401
            return view(*args, **kwargs)

        return wrapped

    @app.get("/api/health")
    def health():
        save_root = store.get().get("save_root", "")
        return jsonify(
            {
                "status": "ok",
                "version": VERSION,
                "save_ready": bool(save_root and Path(save_root).is_dir()),
            }
        )

    @app.post("/api/pair")
    def pair():
        if not _is_extension_origin(request.headers.get("Origin", "")):
            return jsonify({"error": "只允许 Chrome 扩展连接"}), 403
        return jsonify({"token": store.pairing_token, "settings": store.public_settings()})

    @app.route("/api/settings", methods=["GET", "PUT", "OPTIONS"])
    @require_token
    def settings_route():
        if request.method == "GET":
            return jsonify({"settings": store.public_settings()})
        payload = _json_payload()
        try:
            if "save_root" in payload:
                _validate_save_root(payload["save_root"])
            _validate_settings(payload)
        except FolderSelectionError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"settings": store.update(payload)})

    @app.route("/api/settings/choose-folder", methods=["POST", "OPTIONS"])
    @require_token
    def choose_folder_route():
        try:
            selected = select_folder()
            _validate_save_root(selected)
        except FolderSelectionError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"settings": store.update({"save_root": selected})})

    @app.route("/api/pages", methods=["POST", "OPTIONS"])
    @require_token
    def save_page():
        payload = _json_payload()
        metadata = payload.get("metadata")
        content = str(payload.get("content") or "").strip()
        if not isinstance(metadata, dict) or not str(metadata.get("title") or "").strip():
            return jsonify({"error": "没有读取到网页标题"}), 400
        if not content:
            return jsonify({"error": "没有读取到可保存的网页正文"}), 400

        ai_result, warning = organize_if_requested(
            content, "page", bool(payload.get("ai_organize"))
        )
        markdown = render_page_markdown(metadata, content, ai_result)
        settings = store.get()
        try:
            path = StorageService(settings.get("save_root", "")).save_markdown(
                settings.get("page_subdir", "网页剪藏"),
                str(metadata.get("title")),
                markdown,
            )
        except StorageError as exc:
            return jsonify({"error": str(exc)}), 400
        return (
            jsonify(
                {
                    "path": str(path),
                    "filename": path.name,
                    "warning": warning,
                }
            ),
            201,
        )

    @app.route("/api/media/jobs", methods=["POST", "OPTIONS"])
    @require_token
    def create_media_job():
        payload = _json_payload()
        url = str(payload.get("url") or "").strip()
        if not url:
            return jsonify({"error": "请粘贴音视频链接"}), 400
        settings = store.get()
        try:
            StorageService(settings.get("save_root", ""))
        except StorageError as exc:
            return jsonify({"error": str(exc)}), 400
        job_id = jobs.submit({"url": url, "ai_organize": bool(payload.get("ai_organize"))})
        return jsonify({"job_id": job_id}), 202

    @app.route("/api/media/jobs/<job_id>", methods=["GET", "OPTIONS"])
    @require_token
    def media_job_status(job_id: str):
        job = jobs.get(job_id)
        if not job:
            return jsonify({"error": "找不到该转写任务"}), 404
        return jsonify(job)

    return app


def _is_extension_origin(origin: str) -> bool:
    return origin.startswith("chrome-extension://") and len(origin) > len("chrome-extension://")


def _json_payload() -> dict[str, Any]:
    if request.mimetype != "application/json":
        return {}
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _validate_save_root(value: Any) -> None:
    path = Path(str(value or "")).expanduser()
    if not str(value or "").strip() or not path.exists() or not path.is_dir():
        raise FolderSelectionError("保存文件夹不存在或不是文件夹")


def _validate_settings(payload: dict[str, Any]) -> None:
    for key in ("page_subdir", "media_subdir"):
        if key not in payload:
            continue
        relative = Path(str(payload[key] or "").strip() or ".")
        if relative.is_absolute() or ".." in relative.parts:
            raise FolderSelectionError("子目录必须位于 Markdown 根目录内")
    if "whisper_model" in payload and payload["whisper_model"] not in {
        "tiny",
        "base",
        "small",
        "medium",
        "large",
    }:
        raise FolderSelectionError("Whisper 模型设置无效")


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=43127, debug=False, threaded=True)
