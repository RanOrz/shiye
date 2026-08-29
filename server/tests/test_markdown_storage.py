import tempfile
import unittest
from pathlib import Path

from server.services.markdown_service import (
    render_media_markdown,
    render_page_markdown,
    sanitize_filename,
)
from server.services.storage_service import StorageError, StorageService


class MarkdownServiceTests(unittest.TestCase):
    def test_page_markdown_contains_yaml_ai_and_original(self):
        markdown = render_page_markdown(
            {
                "title": 'A: "quoted" title',
                "source": "https://example.com/post",
                "author": "Ada",
                "published": "2026-08-30",
                "created": "2026-08-30T10:00:00+08:00",
                "tags": ["inbox", "研究"],
            },
            "原始正文。",
            {"summary": "摘要。", "key_points": ["要点一"], "tags": ["AI标签"]},
        )

        self.assertIn('title: "A: \\"quoted\\" title"', markdown)
        self.assertIn("- \"研究\"", markdown)
        self.assertIn("## 内容摘要\n\n摘要。", markdown)
        self.assertIn("- 要点一", markdown)
        self.assertIn("## 网页正文\n\n原始正文。", markdown)

    def test_media_markdown_keeps_full_transcript(self):
        markdown = render_media_markdown(
            {"title": "访谈", "source": "https://example.com/video", "tags": []},
            "完整逐字稿。",
            None,
        )

        self.assertIn('type: "media"', markdown)
        self.assertIn("## 完整转写\n\n完整逐字稿。", markdown)

    def test_sanitize_filename_removes_unsafe_characters(self):
        self.assertEqual(sanitize_filename('  a/b:c*?"<>|  '), "a b c")
        self.assertEqual(sanitize_filename("..."), "未命名")


class StorageServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.storage = StorageService(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_saves_under_requested_subdirectory_and_uniquifies(self):
        first = self.storage.save_markdown("网页剪藏", "标题", "first")
        second = self.storage.save_markdown("网页剪藏", "标题", "second")

        self.assertEqual(first.name, "标题.md")
        self.assertEqual(second.name, "标题 (2).md")
        self.assertEqual(first.read_text(encoding="utf-8"), "first")
        self.assertEqual(second.read_text(encoding="utf-8"), "second")

    def test_rejects_path_traversal(self):
        with self.assertRaises(StorageError):
            self.storage.save_markdown("../outside", "bad", "content")

    def test_requires_configured_root(self):
        with self.assertRaises(StorageError):
            StorageService("")


if __name__ == "__main__":
    unittest.main()
