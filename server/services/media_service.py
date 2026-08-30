from __future__ import annotations

import ipaddress
import re
import socket
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse


ProgressCallback = Callable[[str, str], None]


class MediaServiceError(RuntimeError):
    def __init__(self, message: str, code: str = "MEDIA_ERROR"):
        super().__init__(message)
        self.code = code


@dataclass
class MediaResult:
    title: str
    author: str
    transcript: str
    method: str
    duration: int | float | None = None


def extract_youtube_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        else:
            match = re.match(r"/(?:embed|shorts|live)/([A-Za-z0-9_-]{11})", parsed.path)
            candidate = match.group(1) if match else ""
    else:
        return None
    return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate or "") else None


def validate_public_url(url: str, resolve_dns: bool = True) -> str:
    try:
        parsed = urlparse(url.strip())
    except ValueError as exc:
        raise MediaServiceError("链接格式无效") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise MediaServiceError("只支持公开的 HTTP 或 HTTPS 音视频链接")

    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".local"):
        raise MediaServiceError("不允许访问本机或局域网地址")

    def ensure_global(address: str) -> None:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return
        if not ip.is_global:
            raise MediaServiceError("不允许访问本机或局域网地址")

    ensure_global(host)
    if resolve_dns:
        try:
            addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
        except socket.gaierror as exc:
            raise MediaServiceError("无法解析链接域名") from exc
        for address in addresses:
            ensure_global(address[4][0])
    return parsed.geturl()


class MediaService:
    _models: dict[str, Any] = {}
    _model_lock = threading.Lock()

    def transcribe(
        self,
        url: str,
        whisper_model: str,
        progress: ProgressCallback | None = None,
    ) -> MediaResult:
        notify = progress or (lambda _stage, _detail: None)
        safe_url = validate_public_url(url)
        notify("metadata", "正在读取媒体信息")
        metadata = self._extract_metadata(safe_url)
        youtube_id = extract_youtube_id(safe_url)

        if youtube_id:
            notify("captions", "正在查找视频字幕")
            transcript = self._fetch_youtube_transcript(youtube_id)
            if transcript:
                return MediaResult(
                    title=str(metadata.get("title") or youtube_id),
                    author=str(metadata.get("author") or ""),
                    transcript=transcript,
                    method="captions",
                    duration=metadata.get("duration"),
                )

        notify("captions", "正在查找平台字幕")
        transcript = self._fetch_ytdlp_subtitle(safe_url)
        if transcript:
            return MediaResult(
                title=str(metadata.get("title") or "未命名音视频"),
                author=str(metadata.get("author") or ""),
                transcript=transcript,
                method="captions",
                duration=metadata.get("duration"),
            )

        notify("downloading", "没有可用字幕，正在提取音频")
        return self._download_and_transcribe(safe_url, whisper_model, metadata, notify)

    @staticmethod
    def _extract_metadata(url: str) -> dict[str, Any]:
        try:
            import yt_dlp

            with yt_dlp.YoutubeDL(
                {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
            ) as ydl:
                info = ydl.extract_info(url, download=False)
            return {
                "title": info.get("title") or "未命名音视频",
                "author": info.get("uploader") or info.get("channel") or "",
                "duration": info.get("duration"),
            }
        except Exception as exc:
            raise MediaServiceError(f"无法读取音视频信息：{exc}", "MEDIA_METADATA") from exc

    @staticmethod
    def _fetch_youtube_transcript(video_id: str) -> str:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            transcript = YouTubeTranscriptApi().fetch(
                video_id, languages=["zh-Hans", "zh-CN", "zh-TW", "zh", "en"]
            )
            return " ".join(item.text.strip() for item in transcript if item.text.strip())
        except Exception:
            return ""

    @staticmethod
    def _fetch_ytdlp_subtitle(url: str) -> str:
        """Try platform-provided subtitles without downloading the media stream."""
        try:
            import yt_dlp

            with tempfile.TemporaryDirectory(prefix="local-web-clipper-captions-") as temp_dir:
                output_template = str(Path(temp_dir) / "captions.%(ext)s")
                options = {
                    "quiet": True,
                    "no_warnings": True,
                    "skip_download": True,
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": ["zh-Hans", "zh-CN", "zh-TW", "zh", "en"],
                    "subtitlesformat": "vtt",
                    "outtmpl": output_template,
                    "noplaylist": True,
                }
                with yt_dlp.YoutubeDL(options) as ydl:
                    ydl.download([url])
                subtitle_files = sorted(Path(temp_dir).glob("*.vtt"), key=lambda path: path.stat().st_size, reverse=True)
                if not subtitle_files:
                    return ""
                return MediaService._parse_vtt(subtitle_files[0].read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return ""

    @staticmethod
    def _parse_vtt(value: str) -> str:
        lines: list[str] = []
        previous = ""
        for raw in value.splitlines():
            line = raw.strip()
            if not line or line == "WEBVTT" or "-->" in line or line.isdigit() or line.startswith(("NOTE", "STYLE", "REGION")):
                continue
            line = re.sub(r"<[^>]+>", "", line)
            line = re.sub(r"&(?:amp|lt|gt|quot);", lambda match: {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"'}[match.group(0)], line)
            line = re.sub(r"\s+", " ", line).strip()
            if line and line != previous:
                lines.append(line)
                previous = line
        return " ".join(lines).strip()

    def _download_and_transcribe(
        self,
        url: str,
        whisper_model: str,
        metadata: dict[str, Any],
        progress: ProgressCallback,
    ) -> MediaResult:
        try:
            import yt_dlp

            with tempfile.TemporaryDirectory(prefix="local-web-clipper-") as temp_dir:
                output_template = str(Path(temp_dir) / "media.%(ext)s")
                with yt_dlp.YoutubeDL(
                    {
                        "format": "bestaudio/best",
                        "outtmpl": output_template,
                        "quiet": True,
                        "no_warnings": True,
                        "noplaylist": True,
                    }
                ) as ydl:
                    info = ydl.extract_info(url, download=True)
                    prepared = Path(ydl.prepare_filename(info))

                audio_path = prepared if prepared.exists() else self._find_downloaded_file(Path(temp_dir))
                progress("transcribing", f"正在使用 Whisper {whisper_model} 转写")
                model = self._load_whisper_model(whisper_model)
                result = model.transcribe(str(audio_path), fp16=False)
                transcript = str(result.get("text") or "").strip()
                if not transcript:
                    raise MediaServiceError("Whisper 没有识别出文字", "MEDIA_TRANSCRIBE_EMPTY")
                return MediaResult(
                    title=str(info.get("title") or metadata.get("title") or "未命名音视频"),
                    author=str(
                        info.get("uploader")
                        or info.get("channel")
                        or metadata.get("author")
                        or ""
                    ),
                    transcript=transcript,
                    method="whisper",
                    duration=info.get("duration") or metadata.get("duration"),
                )
        except MediaServiceError:
            raise
        except Exception as exc:
            detail = str(exc)
            if "403" in detail or "Forbidden" in detail:
                raise MediaServiceError("平台拒绝下载媒体（HTTP 403）。请确认视频可公开访问，或在浏览器登录后重试", "MEDIA_DOWNLOAD_403") from exc
            raise MediaServiceError(f"音视频下载或转写失败：{exc}", "MEDIA_DOWNLOAD_OR_TRANSCRIBE") from exc

    @classmethod
    def _load_whisper_model(cls, model_name: str):
        if model_name not in {"tiny", "base", "small", "medium", "large"}:
            raise MediaServiceError("Whisper 模型设置无效", "MEDIA_WHISPER_MODEL")
        with cls._model_lock:
            if model_name not in cls._models:
                import whisper

                cls._models[model_name] = whisper.load_model(model_name)
            return cls._models[model_name]

    @staticmethod
    def _find_downloaded_file(folder: Path) -> Path:
        candidates = [path for path in folder.iterdir() if path.is_file() and not path.name.endswith(".part")]
        if not candidates:
            raise MediaServiceError("没有找到下载后的音频文件")
        return max(candidates, key=lambda path: path.stat().st_size)
