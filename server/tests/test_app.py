import tempfile
import unittest
from pathlib import Path

from server.app import create_app
from server.services.ai_service import AIServiceError
from server.services.media_service import MediaResult


class StubMediaService:
    def transcribe(self, url, whisper_model, progress):
        progress("captions", "读取字幕")
        return MediaResult(
            title="测试视频",
            author="测试频道",
            transcript="测试转写正文。",
            method="captions",
            duration=61,
        )


class StubAIService:
    def __init__(self, fail=False):
        self.fail = fail

    def organize(self, text, settings, note_type):
        if self.fail:
            raise AIServiceError("AI 暂时不可用")
        if not settings.get("enabled"):
            return None
        return {"summary": "自动摘要", "key_points": ["要点"], "tags": ["自动标签"]}


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.save_root = self.root / "notes"
        self.save_root.mkdir()
        self.config_path = self.root / "config.json"
        self.origin = "chrome-extension://abcdefghijklmnop"
        self.app = create_app(
            config_path=self.config_path,
            media_service=StubMediaService(),
            ai_service=StubAIService(),
            folder_selector=lambda: str(self.save_root),
        )
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()
        pair = self.client.post("/api/pair", headers={"Origin": self.origin})
        self.assertEqual(pair.status_code, 200)
        self.token = pair.get_json()["token"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def auth_headers(self):
        return {"Origin": self.origin, "X-Local-Clipper-Key": self.token}

    def configure_save_root(self):
        response = self.client.put(
            "/api/settings",
            headers=self.auth_headers(),
            json={"save_root": str(self.save_root)},
        )
        self.assertEqual(response.status_code, 200)

    def test_health_is_public_but_settings_require_token(self):
        health = self.client.get("/api/health")
        unauthorized = self.client.get("/api/settings", headers={"Origin": self.origin})

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["status"], "ok")
        self.assertEqual(unauthorized.status_code, 401)

    def test_pairing_rejects_normal_web_pages(self):
        response = self.client.post("/api/pair", headers={"Origin": "https://evil.example"})
        self.assertEqual(response.status_code, 403)

    def test_settings_hide_key_and_choose_folder(self):
        response = self.client.post("/api/settings/choose-folder", headers=self.auth_headers())
        settings = response.get_json()["settings"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(settings["save_root"], str(self.save_root))
        self.assertNotIn("api_key", settings["ai"])

    def test_page_save_writes_markdown_to_selected_folder(self):
        self.configure_save_root()
        response = self.client.post(
            "/api/pages",
            headers=self.auth_headers(),
            json={
                "metadata": {
                    "title": "测试文章",
                    "source": "https://example.com/article",
                    "author": "作者",
                    "tags": ["inbox"],
                },
                "content": "网页正文。",
                "ai_organize": False,
            },
        )

        self.assertEqual(response.status_code, 201)
        saved = Path(response.get_json()["path"])
        self.assertTrue(saved.exists())
        self.assertIn("网页正文。", saved.read_text(encoding="utf-8"))

    def test_ai_failure_does_not_block_page_save(self):
        app = create_app(
            config_path=self.config_path,
            media_service=StubMediaService(),
            ai_service=StubAIService(fail=True),
            folder_selector=lambda: str(self.save_root),
        )
        app.config.update(TESTING=True)
        client = app.test_client()
        token = client.post("/api/pair", headers={"Origin": self.origin}).get_json()["token"]
        headers = {"Origin": self.origin, "X-Local-Clipper-Key": token}
        client.put(
            "/api/settings",
            headers=headers,
            json={
                "save_root": str(self.save_root),
                "ai": {"enabled": True, "model": "test", "api_key": "secret"},
            },
        )

        response = client.post(
            "/api/pages",
            headers=headers,
            json={
                "metadata": {"title": "AI 回退"},
                "content": "仍然要保存。",
                "ai_organize": True,
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("AI 暂时不可用", response.get_json()["warning"])
        self.assertTrue(Path(response.get_json()["path"]).exists())

    def test_media_job_finishes_and_saves_markdown(self):
        self.configure_save_root()
        response = self.client.post(
            "/api/media/jobs",
            headers=self.auth_headers(),
            json={"url": "https://example.com/video", "ai_organize": False},
        )

        self.assertEqual(response.status_code, 202)
        job_id = response.get_json()["job_id"]
        job = self.app.extensions["clipper_job_manager"].wait(job_id, timeout=2)
        status = self.client.get(f"/api/media/jobs/{job_id}", headers=self.auth_headers())

        self.assertEqual(job["status"], "done")
        self.assertEqual(status.status_code, 200)
        saved = Path(status.get_json()["result"]["path"])
        self.assertIn("测试转写正文。", saved.read_text(encoding="utf-8"))

    def test_extension_origin_receives_cors_headers(self):
        response = self.client.options(
            "/api/settings",
            headers={
                "Origin": self.origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Local-Clipper-Key",
            },
        )

        self.assertEqual(response.headers["Access-Control-Allow-Origin"], self.origin)
        self.assertIn("X-Local-Clipper-Key", response.headers["Access-Control-Allow-Headers"])


if __name__ == "__main__":
    unittest.main()
