import unittest
from unittest.mock import Mock, patch

from server.services.ai_service import AIService, AIServiceError


class AIServiceTests(unittest.TestCase):
    def test_disabled_ai_returns_none_without_request(self):
        service = AIService()
        with patch("server.services.ai_service.requests.post") as post:
            result = service.organize("正文", {"enabled": False}, "page")
        self.assertIsNone(result)
        post.assert_not_called()

    def test_openai_compatible_response_is_normalized(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '```json\n{"summary":"摘要","key_points":["一","二"],"tags":["标签"]}\n```'
                    }
                }
            ]
        }
        service = AIService()
        with patch("server.services.ai_service.requests.post", return_value=response) as post:
            result = service.organize(
                "正文",
                {
                    "enabled": True,
                    "provider": "openai_compatible",
                    "base_url": "https://example.com/v1",
                    "model": "test-model",
                    "api_key": "secret",
                },
                "page",
            )

        self.assertEqual(result["summary"], "摘要")
        self.assertEqual(result["key_points"], ["一", "二"])
        self.assertEqual(result["tags"], ["标签"])
        request_url = post.call_args.args[0]
        self.assertEqual(request_url, "https://example.com/v1/chat/completions")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer secret")

    def test_ollama_response_is_supported(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "message": {
                "content": '{"summary":"本地摘要","key_points":[],"tags":[]}'
            }
        }
        service = AIService()
        with patch("server.services.ai_service.requests.post", return_value=response) as post:
            result = service.organize(
                "正文",
                {
                    "enabled": True,
                    "provider": "ollama",
                    "base_url": "http://127.0.0.1:11434",
                    "model": "qwen3:8b",
                    "api_key": "",
                },
                "media",
            )

        self.assertEqual(result["summary"], "本地摘要")
        self.assertEqual(post.call_args.args[0], "http://127.0.0.1:11434/api/chat")

    def test_malformed_model_output_raises_clear_error(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"choices": [{"message": {"content": "not json"}}]}
        service = AIService()

        with patch("server.services.ai_service.requests.post", return_value=response):
            with self.assertRaises(AIServiceError):
                service.organize(
                    "正文",
                    {
                        "enabled": True,
                        "provider": "openai_compatible",
                        "base_url": "https://example.com/v1",
                        "model": "test",
                        "api_key": "secret",
                    },
                    "page",
                )


if __name__ == "__main__":
    unittest.main()

