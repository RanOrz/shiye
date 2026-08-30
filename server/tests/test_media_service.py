import socket
import unittest
from unittest.mock import patch

from server.services.media_service import (
    MediaResult,
    MediaService,
    MediaServiceError,
    extract_youtube_id,
    validate_public_url,
)


class MediaServiceTests(unittest.TestCase):
    def test_extracts_common_youtube_urls(self):
        self.assertEqual(extract_youtube_id("https://youtu.be/4w62c3QIugE?t=1"), "4w62c3QIugE")
        self.assertEqual(
            extract_youtube_id("https://www.youtube.com/watch?v=40M-66LgKTI"),
            "40M-66LgKTI",
        )
        self.assertIsNone(extract_youtube_id("https://example.com/video"))

    def test_rejects_non_http_and_private_network_urls(self):
        with self.assertRaises(MediaServiceError) as invalid:
            validate_public_url("file:///tmp/video.mp4", resolve_dns=False)
        self.assertEqual(invalid.exception.code, "MEDIA_URL_INVALID")
        with self.assertRaises(MediaServiceError) as private:
            validate_public_url("http://127.0.0.1/private", resolve_dns=False)
        self.assertEqual(private.exception.code, "MEDIA_URL_PRIVATE")

    def test_rejects_hostname_resolving_to_private_address(self):
        with patch(
            "server.services.media_service.socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.2", 443))],
        ):
            with self.assertRaises(MediaServiceError):
                validate_public_url("https://internal.example")

    def test_uses_youtube_subtitles_before_whisper(self):
        service = MediaService()
        progress = []
        with (
            patch.object(service, "_extract_metadata", return_value={"title": "演讲", "author": "频道"}),
            patch.object(service, "_fetch_youtube_transcript", return_value="字幕正文") as captions,
            patch.object(service, "_download_and_transcribe") as fallback,
            patch(
                "server.services.media_service.validate_public_url",
                side_effect=lambda url: url,
            ),
        ):
            result = service.transcribe(
                "https://youtu.be/4w62c3QIugE", "base", lambda stage, detail: progress.append(stage)
            )

        self.assertEqual(result.transcript, "字幕正文")
        self.assertEqual(result.method, "captions")
        captions.assert_called_once()
        fallback.assert_not_called()
        self.assertIn("captions", progress)

    def test_falls_back_to_whisper_when_captions_are_missing(self):
        service = MediaService()
        fallback_result = MediaResult(
            title="访谈", author="", transcript="本地转写", method="whisper", duration=12
        )
        with (
            patch.object(service, "_extract_metadata", return_value={"title": "访谈", "author": ""}),
            patch.object(service, "_fetch_youtube_transcript", return_value=""),
            patch.object(service, "_fetch_ytdlp_subtitle", return_value=""),
            patch.object(service, "_download_and_transcribe", return_value=fallback_result) as fallback,
            patch(
                "server.services.media_service.validate_public_url",
                side_effect=lambda url: url,
            ),
        ):
            result = service.transcribe("https://youtu.be/4w62c3QIugE", "base")

        self.assertEqual(result.transcript, "本地转写")
        fallback.assert_called_once()

    def test_supports_bilibili_subtitles_before_whisper(self):
        service = MediaService()
        with (
            patch.object(service, "_extract_metadata", return_value={"title": "哔哩哔哩视频", "author": "UP主"}),
            patch.object(service, "_fetch_ytdlp_subtitle", return_value="字幕正文"),
            patch.object(service, "_download_and_transcribe") as fallback,
            patch("server.services.media_service.validate_public_url", side_effect=lambda url: url),
        ):
            result = service.transcribe("https://www.bilibili.com/video/BV1xx411c7mD", "base")

        self.assertEqual(result.transcript, "字幕正文")
        self.assertEqual(result.method, "captions")
        fallback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
