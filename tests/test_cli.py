import json
from unittest.mock import patch

import pytest

from vocap.cli import _collect_urls, main
from vocap.errors import VoCapError
from vocap.models import Segment, Transcript, VideoInfo


def _mock_extract_result():
    info = VideoInfo("7380123456789012345", "douyin", "https://v.douyin.com/x/")
    transcript = Transcript(
        text="你好世界",
        segments=[Segment(0.0, 2.0, "你好世界")],
        language="zh",
        duration=2.0,
    )
    return info, transcript, 1.5


class TestCollectUrls:
    def test_extracts_url_from_share_text(self):
        urls = _collect_urls(["https://v.douyin.com/iRNBho5/"])
        assert len(urls) == 1
        assert "v.douyin.com" in urls[0]

    def test_ignores_non_douyin_text(self):
        urls = _collect_urls(["hello world no url here"])
        assert urls == []

    def test_reads_urls_from_file(self, tmp_path):
        f = tmp_path / "urls.txt"
        f.write_text("https://v.douyin.com/abc/\n# comment\nhttps://v.douyin.com/def/\n")
        urls = _collect_urls([str(f)])
        assert len(urls) == 2

    def test_skips_blank_lines_and_comments(self, tmp_path):
        f = tmp_path / "urls.txt"
        f.write_text("\n# comment\n\nhttps://v.douyin.com/abc/\n\n")
        urls = _collect_urls([str(f)])
        assert len(urls) == 1


class TestMain:
    @patch("vocap.cli.extract", return_value=_mock_extract_result())
    def test_single_url_outputs_json(self, mock_extract, capsys):
        with patch("sys.argv", ["vocap", "https://v.douyin.com/test/"]):
            main()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["video_id"] == "7380123456789012345"

    @patch("vocap.cli.extract", return_value=_mock_extract_result())
    def test_output_to_file(self, mock_extract, tmp_path):
        outfile = str(tmp_path / "result.json")
        with patch("sys.argv", ["vocap", "https://v.douyin.com/test/", "-o", outfile]):
            main()
        assert (tmp_path / "result.json").exists()
        data = json.loads((tmp_path / "result.json").read_text())
        assert data["video_id"] == "7380123456789012345"

    @patch("vocap.cli.extract", side_effect=VoCapError("test error"))
    def test_single_url_failure_exits_1(self, mock_extract):
        with patch("sys.argv", ["vocap", "https://v.douyin.com/test/"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_no_valid_urls_exits(self):
        with patch("sys.argv", ["vocap", "not-a-url"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0

    @patch("vocap.cli.extract", return_value=_mock_extract_result())
    def test_format_markdown(self, mock_extract, capsys):
        with patch("sys.argv", ["vocap", "https://v.douyin.com/test/", "-f", "markdown"]):
            main()
        out = capsys.readouterr().out
        assert "# 视频文案" in out

    @patch("vocap.cli.extract", return_value=_mock_extract_result())
    def test_passes_cookies_from_browser(self, mock_extract):
        with patch(
            "sys.argv",
            ["vocap", "https://v.douyin.com/test/", "--cookies-from-browser", "chrome"],
        ):
            main()
        assert mock_extract.call_args.kwargs["cookies_from_browser"] == "chrome"


class TestBatchMode:
    @patch("vocap.cli.time.sleep")
    @patch("vocap.cli.extract")
    def test_partial_failure_exits_2(self, mock_extract, mock_sleep):
        """批量模式部分失败时 exit code 为 2。"""
        mock_extract.side_effect = [
            _mock_extract_result(),
            VoCapError("second failed"),
        ]
        with patch("sys.argv", ["vocap", "https://v.douyin.com/a/", "https://v.douyin.com/b/"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

    @patch("vocap.cli.time.sleep")
    @patch("vocap.cli.extract")
    def test_all_fail_exits_1(self, mock_extract, mock_sleep):
        """批量模式全部失败时 exit code 为 1。"""
        mock_extract.side_effect = [
            VoCapError("first failed"),
            VoCapError("second failed"),
        ]
        with patch("sys.argv", ["vocap", "https://v.douyin.com/a/", "https://v.douyin.com/b/"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch("vocap.cli.time.sleep")
    @patch("vocap.cli.extract", return_value=_mock_extract_result())
    def test_sleeps_between_batch_items(self, mock_extract, mock_sleep, capsys):
        with patch(
            "sys.argv",
            ["vocap", "https://v.douyin.com/a/", "https://v.douyin.com/b/", "--sleep", "2"],
        ):
            main()
        mock_sleep.assert_called_once_with(2.0)
        err = capsys.readouterr().err
        assert err.find("距上一条间隔") < err.find("[2/2]")

    @patch("vocap.cli.extract", return_value=_mock_extract_result())
    def test_passes_download_retries(self, mock_extract):
        with patch("sys.argv", ["vocap", "https://v.douyin.com/test/", "--retries", "5"]):
            main()
        assert mock_extract.call_args.kwargs["download_retries"] == 5

    def test_rejects_negative_retries(self):
        with patch("sys.argv", ["vocap", "https://v.douyin.com/test/", "--retries", "-1"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0

    def test_rejects_cookies_and_browser_together(self, tmp_path):
        cookie = tmp_path / "cookies.txt"
        cookie.write_text("# Netscape HTTP Cookie File\n")
        with patch(
            "sys.argv",
            [
                "vocap",
                "https://v.douyin.com/test/",
                "--cookies-from-browser",
                "chrome",
                "--cookies",
                str(cookie),
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0
