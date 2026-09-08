from unittest.mock import patch

import pytest

from vocap.errors import AudioDownloadError, TranscriptionError, UnsupportedPlatformError
from vocap.models import Segment, Transcript
from vocap.pipeline import extract, is_transient_download_error


def _mock_transcript():
    return Transcript(
        text="ASR转写文案",
        segments=[Segment(0.0, 3.0, "ASR转写文案")],
        language="zh",
        duration=3.0,
    )


class TestExtract:
    @patch("vocap.pipeline.cleanup")
    @patch("vocap.pipeline.transcribe")
    @patch("vocap.pipeline.download_audio")
    @patch("vocap.pipeline.resolve_url")
    def test_happy_path(self, mock_resolve, mock_dl, mock_asr, mock_cleanup, sample_video_info):
        mock_resolve.return_value = sample_video_info
        mock_dl.return_value = "/tmp/audio.wav"
        mock_asr.return_value = _mock_transcript()

        info, transcript, elapsed = extract("https://v.douyin.com/x")

        assert info.video_id == "7380123456789012345"
        assert info.platform == "douyin"
        assert transcript.text == "ASR转写文案"
        assert isinstance(elapsed, float)
        assert elapsed >= 0
        mock_resolve.assert_called_once()
        mock_dl.assert_called_once()
        mock_asr.assert_called_once()
        mock_cleanup.assert_called_once_with("/tmp/audio.wav")
        assert mock_dl.call_args.args[0] == "https://www.douyin.com/video/7380123456789012345"

    @patch("vocap.pipeline.cleanup")
    @patch("vocap.pipeline.transcribe")
    @patch("vocap.pipeline.download_audio")
    @patch("vocap.pipeline.resolve_url")
    def test_passes_browser_cookies_to_downloader(
        self, mock_resolve, mock_dl, mock_asr, mock_cleanup, sample_video_info
    ):
        mock_resolve.return_value = sample_video_info
        mock_dl.return_value = "/tmp/audio.wav"
        mock_asr.return_value = _mock_transcript()

        extract("https://v.douyin.com/x", cookies_from_browser="chrome")

        assert mock_dl.call_args.kwargs["cookies_from_browser"] == "chrome"

    def test_detects_403_as_transient(self):
        err = AudioDownloadError("音频下载失败: HTTP Error 403: Forbidden\nFresh cookies")
        assert is_transient_download_error(err) is True

    def test_detects_fresh_cookies_as_transient(self):
        err = AudioDownloadError("ERROR: Fresh cookies (not necessarily logged in) are needed")
        assert is_transient_download_error(err) is True

    def test_does_not_treat_403_substring_as_transient(self):
        err = AudioDownloadError("无法解析视频 7403")
        assert is_transient_download_error(err) is False

    def test_does_not_treat_forbidden_alone_as_transient(self):
        err = AudioDownloadError("This video is Forbidden")
        assert is_transient_download_error(err) is False

    def test_detects_ffmpeg_error_as_not_transient(self):
        err = AudioDownloadError("ffmpeg 音频转换失败: broken")
        assert is_transient_download_error(err) is False

    @patch("vocap.pipeline.time.sleep")
    @patch("vocap.pipeline.cleanup")
    @patch("vocap.pipeline.transcribe")
    @patch("vocap.pipeline.download_audio")
    @patch("vocap.pipeline.resolve_url")
    def test_retries_transient_download_error(
        self, mock_resolve, mock_dl, mock_asr, mock_cleanup, mock_sleep, sample_video_info
    ):
        mock_resolve.return_value = sample_video_info
        mock_dl.side_effect = [
            AudioDownloadError("ERROR: Fresh cookies (not necessarily logged in) are needed"),
            "/tmp/audio.wav",
        ]
        mock_asr.return_value = _mock_transcript()

        extract("https://v.douyin.com/x", download_retries=3)

        assert mock_dl.call_count == 2
        mock_sleep.assert_called_once()
        mock_asr.assert_called_once()

    @patch("vocap.pipeline.time.sleep")
    @patch("vocap.pipeline.cleanup")
    @patch("vocap.pipeline.transcribe")
    @patch("vocap.pipeline.download_audio")
    @patch("vocap.pipeline.resolve_url")
    def test_does_not_retry_non_transient_download_error(
        self, mock_resolve, mock_dl, mock_asr, mock_cleanup, mock_sleep, sample_video_info
    ):
        mock_resolve.return_value = sample_video_info
        mock_dl.side_effect = AudioDownloadError("下载完成但找不到输出文件")

        with pytest.raises(AudioDownloadError, match="找不到输出文件"):
            extract("https://v.douyin.com/x", download_retries=3)

        assert mock_dl.call_count == 1
        mock_sleep.assert_not_called()
        mock_asr.assert_not_called()

    @patch("vocap.pipeline.time.sleep")
    @patch("vocap.pipeline.cleanup")
    @patch("vocap.pipeline.transcribe")
    @patch("vocap.pipeline.download_audio")
    @patch("vocap.pipeline.resolve_url")
    def test_retries_exhausted_still_fails(
        self, mock_resolve, mock_dl, mock_asr, mock_cleanup, mock_sleep, sample_video_info
    ):
        mock_resolve.return_value = sample_video_info
        mock_dl.side_effect = AudioDownloadError("HTTP Error 403: Forbidden")

        with pytest.raises(AudioDownloadError, match="HTTP Error 403"):
            extract("https://v.douyin.com/x", download_retries=2)

        assert mock_dl.call_count == 3
        assert mock_sleep.call_count == 2
        mock_asr.assert_not_called()

    @patch("vocap.pipeline.cleanup")
    @patch("vocap.pipeline.transcribe")
    @patch("vocap.pipeline.download_audio")
    @patch("vocap.pipeline.resolve_url")
    def test_unsupported_platform_propagates(self, mock_resolve, mock_dl, mock_asr, mock_cleanup):
        mock_resolve.side_effect = UnsupportedPlatformError("不支持")

        with pytest.raises(UnsupportedPlatformError):
            extract("https://youtube.com/watch?v=xxx")

        mock_dl.assert_not_called()
        mock_asr.assert_not_called()

    @patch("vocap.pipeline.cleanup")
    @patch("vocap.pipeline.transcribe")
    @patch("vocap.pipeline.download_audio")
    @patch("vocap.pipeline.resolve_url")
    def test_cleanup_on_asr_failure(
        self, mock_resolve, mock_dl, mock_asr, mock_cleanup, sample_video_info
    ):
        mock_resolve.return_value = sample_video_info
        mock_dl.return_value = "/tmp/audio.wav"
        mock_asr.side_effect = TranscriptionError("ASR 错误")

        with pytest.raises(TranscriptionError, match="ASR 错误"):
            extract("https://v.douyin.com/x")

        mock_cleanup.assert_called_once_with("/tmp/audio.wav")

    @patch("vocap.pipeline.cleanup")
    @patch("vocap.pipeline.transcribe")
    @patch("vocap.pipeline.download_audio")
    @patch("vocap.pipeline.resolve_url")
    def test_status_callback(
        self, mock_resolve, mock_dl, mock_asr, mock_cleanup, sample_video_info
    ):
        mock_resolve.return_value = sample_video_info
        mock_dl.return_value = "/tmp/audio.wav"
        mock_asr.return_value = _mock_transcript()

        messages = []
        extract("https://v.douyin.com/x", on_status=messages.append)

        assert any("解析" in m for m in messages)
        assert any("下载" in m for m in messages)
        assert any("完成" in m for m in messages)

    @patch("vocap.pipeline.cleanup")
    @patch("vocap.pipeline.transcribe")
    @patch("vocap.pipeline.download_audio")
    @patch("vocap.pipeline.resolve_url")
    def test_pipeline_cleans_text(
        self, mock_resolve, mock_dl, mock_asr, mock_cleanup, sample_video_info
    ):
        """验证 pipeline 对 ASR 输出执行清洗。"""
        mock_resolve.return_value = sample_video_info
        mock_dl.return_value = "/tmp/audio.wav"
        dirty = Transcript(
            text="你好 ，世界  。",
            segments=[Segment(0.0, 3.0, "你好 ，世界  。")],
            language="zh",
            duration=3.0,
        )
        mock_asr.return_value = dirty

        _, transcript, _ = extract("https://v.douyin.com/x")

        assert transcript.text == "你好，世界。"
        assert transcript.segments[0].text == "你好，世界。"
