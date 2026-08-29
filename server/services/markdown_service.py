from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from typing import Any


UNSAFE_FILENAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def sanitize_filename(value: str, max_length: int = 120) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = UNSAFE_FILENAME.sub(" ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" .")
    return (normalized[:max_length].rstrip(" .") or "未命名")


def _yaml_string(value: Any) -> str:
    return json.dumps("" if value is None else str(value), ensure_ascii=False)


def _unique_strings(values: list[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            output.append(text)
    return output


def _frontmatter(metadata: dict[str, Any], note_type: str, ai_result: dict[str, Any] | None) -> str:
    created = metadata.get("created") or datetime.now().astimezone().isoformat(timespec="seconds")
    tags = list(metadata.get("tags") or [])
    if ai_result:
        tags.extend(ai_result.get("tags") or [])
    tags = _unique_strings(tags)

    lines = [
        "---",
        f"title: {_yaml_string(metadata.get('title', '未命名'))}",
        f"source: {_yaml_string(metadata.get('source', ''))}",
        f"author: {_yaml_string(metadata.get('author', ''))}",
        f"published: {_yaml_string(metadata.get('published', ''))}",
        f"created: {_yaml_string(created)}",
        f"type: {_yaml_string(note_type)}",
    ]
    if tags:
        lines.append("tags:")
        lines.extend(f"  - {_yaml_string(tag)}" for tag in tags)
    else:
        lines.append("tags: []")
    lines.extend(["---", ""])
    return "\n".join(lines)


def _ai_sections(ai_result: dict[str, Any] | None) -> list[str]:
    if not ai_result:
        return []
    sections: list[str] = []
    summary = str(ai_result.get("summary") or "").strip()
    if summary:
        sections.extend(["## 内容摘要", "", summary, ""])
    points = _unique_strings(list(ai_result.get("key_points") or []))
    if points:
        sections.extend(["## 核心要点", ""])
        sections.extend(f"- {point}" for point in points)
        sections.append("")
    return sections


def render_page_markdown(
    metadata: dict[str, Any], content: str, ai_result: dict[str, Any] | None = None
) -> str:
    title = str(metadata.get("title") or "未命名").strip()
    lines = [_frontmatter(metadata, "page", ai_result), f"# {title}", ""]
    lines.extend(_ai_sections(ai_result))
    lines.extend(["## 网页正文", "", content.strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_media_markdown(
    metadata: dict[str, Any], transcript: str, ai_result: dict[str, Any] | None = None
) -> str:
    title = str(metadata.get("title") or "未命名").strip()
    lines = [_frontmatter(metadata, "media", ai_result), f"# {title}", ""]
    lines.extend(_ai_sections(ai_result))
    lines.extend(["## 完整转写", "", transcript.strip(), ""])
    return "\n".join(lines).rstrip() + "\n"

