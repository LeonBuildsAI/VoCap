import os
import tempfile
from unittest.mock import patch

import pytest

from vocap.downloader import (
    _download_with_ytdlp,
    _find_downloaded_file,
    check_ffmpeg,
    cleanup,
    download_audio,
    parse_cookies_from_browser,
)
from vocap.errors import AudioDownloadError, FFmpegNotFoundError


class TestCheckFfmpeg:
    @patch("shutil.which", return_value="/usr/local/bin/ffmpeg")
    def test_ffmpeg_found(self, mock_which):
        assert check_ffmpeg() is True

    @patch("shutil.which", return_value=None)
    def test_ffmpeg_not_found(self, mock_which):
        assert check_ffmpeg() is False

    @patch("shutil.which", return_value=None)
    def test_ffmpeg_not_found_raises(self, mock_which):
        from vocap.downloader import require_ffmpeg

        with pytest.raises(FFmpegNotFoundError, match="ffmpeg"):
            require_ffmpeg()


class TestFindDownloadedFile:
    def test_find_by_exact_name(self):
        with tempfile.TemporaryDirectory(prefix="vocap_") as tmpdir:
            path = os.path.join(tmpdir, "video.m4a")
            open(path, "w").close()
            assert _find_downloaded_file(path) == path

    def test_find_with_different_extension(self):
        with tempfile.TemporaryDirectory(prefix="vocap_") as tmpdir:
            expected = os.path.join(tmpdir, "video.m4a")
            actual = os.path.join(tmpdir, "video.webm")
            open(actual, "w").close()
            assert _find_downloaded_file(expected) == actual

    def test_file_not_found(self):
        with tempfile.TemporaryDirectory(prefix="vocap_") as tmpdir:
            expected = os.path.join(tmpdir, "nonexistent.m4a")
            assert _find_downloaded_file(expected) is None


class TestCleanup:
    def test_cleanup_removes_temp_dir(self):
        tmpdir = tempfile.mkdtemp(prefix="vocap_")
        audio_path = os.path.join(tmpdir, "audio.wav")
        open(audio_path, "w").close()
        cleanup(audio_path)
        assert not os.path.exists(tmpdir)

    def test_cleanup_ignores_non_temp(self):
        cleanup("/some/random/path/audio.wav")

    def test_cleanup_handles_missing_dir(self):
        cleanup("/tmp/vocap_already_gone/audio.wav")


class TestDownloadAudio:
    @patch("vocap.downloader.require_ffmpeg")
    @patch("vocap.downloader._convert_to_wav16k")
    @patch("vocap.downloader._download_with_ytdlp")
    def test_happy_path(self, mock_ytdlp, mock_convert, mock_ffmpeg):
        mock_ytdlp.return_value = "/tmp/vocap_xxx/video.m4a"

        result = download_audio("https://example.com/video")

        mock_ffmpeg.assert_called_once()
        mock_ytdlp.assert_called_once()
        mock_convert.assert_called_once()
        assert result.endswith("audio_16k.wav")

    @patch("vocap.downloader.require_ffmpeg", side_effect=FFmpegNotFoundError("no ffmpeg"))
    def test_raises_on_missing_ffmpeg(self, mock_ffmpeg):
        with pytest.raises(FFmpegNotFoundError):
            download_audio("https://example.com/video")

    @patch("vocap.downloader.require_ffmpeg")
    @patch("vocap.downloader._download_with_ytdlp", side_effect=AudioDownloadError("fail"))
    def test_cleans_up_on_download_error(self, mock_ytdlp, mock_ffmpeg):
        with pytest.raises(AudioDownloadError):
            download_audio("https://example.com/video")


class TestYtdlpCookieOpts:
    def _run_download(self, tmp_path, **kwargs):
        captured: dict = {}
        out = tmp_path / "vid.m4a"
        out.write_bytes(b"audio")

        class FakeYDL:
            def __init__(self, opts):
                captured.update(opts)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def extract_info(self, url, download=True):
                return {"id": "vid", "ext": "m4a"}

            def prepare_filename(self, info):
                return str(out)

        with patch("vocap.downloader.yt_dlp.YoutubeDL", FakeYDL):
            _download_with_ytdlp("https://www.douyin.com/video/1", str(tmp_path), **kwargs)
        return captured

    def test_passes_cookies_from_browser(self, tmp_path):
        opts = self._run_download(tmp_path, cookies_from_browser="chrome")
        assert opts["cookiesfrombrowser"] == ("chrome", None, None, None)

    def test_passes_browser_profile(self, tmp_path):
        opts = self._run_download(tmp_path, cookies_from_browser="chrome:Default")
        assert opts["cookiesfrombrowser"] == ("chrome", "Default", None, None)

    def test_parse_browser_profile_with_space(self):
        assert parse_cookies_from_browser("chrome:Profile 1") == (
            "chrome",
            "Profile 1",
            None,
            None,
        )

    def test_parse_invalid_browser_spec_raises(self):
        with pytest.raises(AudioDownloadError, match="无效的浏览器 cookie"):
            parse_cookies_from_browser(":::")

    def test_passes_cookie_file(self, tmp_path):
        cookie = tmp_path / "cookies.txt"
        cookie.write_text("# Netscape HTTP Cookie File\n")
        opts = self._run_download(tmp_path, cookiefile=str(cookie))
        assert opts["cookiefile"] == str(cookie)

    def test_omits_cookie_opts_by_default(self, tmp_path):
        opts = self._run_download(tmp_path)
        assert "cookiesfrombrowser" not in opts
        assert "cookiefile" not in opts
