import json
import os
import tempfile
import unittest
from pathlib import Path

from server.config_store import ConfigStore


class ConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_creates_defaults_and_pairing_token(self):
        store = ConfigStore(self.config_path)

        settings = store.public_settings()

        self.assertEqual(settings["page_subdir"], "网页剪藏")
        self.assertEqual(settings["media_subdir"], "视频转写")
        self.assertEqual(settings["whisper_model"], "base")
        self.assertFalse(settings["ai"]["has_api_key"])
        self.assertGreater(len(store.pairing_token), 30)
        self.assertTrue(self.config_path.exists())
        self.assertEqual(os.stat(self.config_path).st_mode & 0o777, 0o600)

    def test_public_settings_never_expose_api_key(self):
        store = ConfigStore(self.config_path)
        store.update({"ai": {"api_key": "top-secret", "model": "small-model"}})

        public = store.public_settings()

        self.assertNotIn("api_key", public["ai"])
        self.assertTrue(public["ai"]["has_api_key"])
        self.assertNotIn("top-secret", json.dumps(public))

    def test_blank_api_key_preserves_saved_secret(self):
        store = ConfigStore(self.config_path)
        store.update({"ai": {"api_key": "keep-me"}})

        store.update({"ai": {"api_key": "", "model": "new-model"}})

        self.assertEqual(store.get()["ai"]["api_key"], "keep-me")
        self.assertEqual(store.get()["ai"]["model"], "new-model")

    def test_update_ignores_unknown_fields(self):
        store = ConfigStore(self.config_path)

        store.update({"page_subdir": "文章", "unknown": "value"})

        self.assertEqual(store.get()["page_subdir"], "文章")
        self.assertNotIn("unknown", store.get())


if __name__ == "__main__":
    unittest.main()

