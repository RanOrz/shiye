from __future__ import annotations

import json
import re
from typing import Any

import requests


class AIServiceError(RuntimeError):
    pass


class AIService:
    def __init__(self, timeout: int = 90, max_chars: int = 120_000):
        self.timeout = timeout
        self.max_chars = max_chars

    def organize(
        self, text: str, settings: dict[str, Any], note_type: str
    ) -> dict[str, Any] | None:
        if not settings.get("enabled"):
            return None
        model = str(settings.get("model") or "").strip()
        if not model:
            raise AIServiceError("已开启 AI 整理，但尚未设置模型名称")

        provider = settings.get("provider", "openai_compatible")
        prompt = self._prompt(text[: self.max_chars], note_type)
        try:
            if provider == "ollama":
                content = self._call_ollama(prompt, settings, model)
            elif provider == "openai_compatible":
                content = self._call_openai_compatible(prompt, settings, model)
            else:
                raise AIServiceError(f"不支持的 AI 服务类型：{provider}")
        except requests.RequestException as exc:
            raise AIServiceError(f"AI 服务请求失败：{exc}") from exc
        return self._parse_result(content)

    def _call_openai_compatible(
        self, prompt: str, settings: dict[str, Any], model: str
    ) -> str:
        base_url = str(settings.get("base_url") or "").strip().rstrip("/")
        api_key = str(settings.get("api_key") or "").strip()
        if not base_url:
            raise AIServiceError("请设置 AI 服务地址")
        if not api_key:
            raise AIServiceError("请设置 AI API Key")
        endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
        response = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是严谨的知识整理助手。只返回合法 JSON，不补充解释。",
                    },
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        try:
            return str(response.json()["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AIServiceError("AI 服务返回格式不正确") from exc

    def _call_ollama(self, prompt: str, settings: dict[str, Any], model: str) -> str:
        base_url = str(settings.get("base_url") or "http://127.0.0.1:11434").strip().rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
        response = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "stream": False,
                "format": "json",
                "messages": [
                    {
                        "role": "system",
                        "content": "你是严谨的知识整理助手。只返回合法 JSON，不补充解释。",
                    },
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        try:
            return str(response.json()["message"]["content"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AIServiceError("Ollama 返回格式不正确") from exc

    @staticmethod
    def _prompt(text: str, note_type: str) -> str:
        source_name = "音视频转写" if note_type == "media" else "网页正文"
        return f"""请整理下面的{source_name}，不得添加原文没有的信息。
返回 JSON 对象，格式必须是：
{{
  "summary": "一段简洁摘要",
  "key_points": ["3到8条核心要点"],
  "tags": ["2到6个短标签"]
}}

原文：
{text}"""

    @staticmethod
    def _parse_result(content: str) -> dict[str, Any]:
        cleaned = content.strip()
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, re.IGNORECASE)
        if fenced:
            cleaned = fenced.group(1).strip()
        if not cleaned.startswith("{"):
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start >= 0 and end > start:
                cleaned = cleaned[start : end + 1]
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AIServiceError("AI 没有返回可解析的 JSON") from exc
        if not isinstance(data, dict):
            raise AIServiceError("AI 整理结果必须是 JSON 对象")

        summary = str(data.get("summary") or "").strip()
        key_points = [str(item).strip() for item in data.get("key_points", []) if str(item).strip()]
        tags = [str(item).strip() for item in data.get("tags", []) if str(item).strip()]
        return {
            "summary": summary,
            "key_points": key_points[:10],
            "tags": tags[:8],
        }

