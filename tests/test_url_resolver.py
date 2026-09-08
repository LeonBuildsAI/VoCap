# tests/test_url_resolver.py
from unittest.mock import patch

import httpx
import pytest

from vocap.errors import UnsupportedPlatformError, URLParseError, URLResolveError
from vocap.models import VideoInfo
from vocap.url_resolver import (
    canonical_watch_url,
    detect_platform,
    extract_douyin_id,
    extract_url_from_text,
    resolve_url,
)

# ===== extract_url_from_text tests =====


class TestExtractUrlFromText:
    def test_share_text_with_noise(self):
        text = (
            " 7.46 复制打开抖音，看看【7cry的作品】🥚你是自由的鸟 去天际吧 "
            "# 原声配音 # dan... https://v.douyin.com/X2rzKBxWv98/ "
            "hod:/ j@P.kc 11/29 :1pm "
        )
        assert extract_url_from_text(text) == "https://v.douyin.com/X2rzKBxWv98/"

    def test_variant_share_text(self):
        text = "6.18 Lkn:/ 复制打开抖音，看看【xxx的作品】 https://v.douyin.com/iRNBho5/ 嘿嘿"
        assert extract_url_from_text(text) == "https://v.douyin.com/iRNBho5/"

    def test_pure_short_url(self):
        url = "https://v.douyin.com/iRNBho5/"
        assert extract_url_from_text(url) == url

    def test_pure_long_url(self):
        text = "看这个视频 https://www.douyin.com/video/7380123456789012345 很好看"
        assert extract_url_from_text(text) == "https://www.douyin.com/video/7380123456789012345"

    def test_empty_string(self):
        assert extract_url_from_text("") is None

    def test_no_url(self):
        assert extract_url_from_text("这段文字里没有链接") is None

    def test_non_douyin_url(self):
        assert extract_url_from_text("看 https://youtube.com/watch?v=xxx") is None

    def test_multiple_douyin_urls(self):
        text = "链接1 https://v.douyin.com/aaa/ 链接2 https://v.douyin.com/bbb/"
        assert extract_url_from_text(text) == "https://v.douyin.com/aaa/"

    def test_leading_trailing_whitespace(self):
        assert (
            extract_url_from_text("  https://v.douyin.com/iRNBho5/  ")
            == "https://v.douyin.com/iRNBho5/"
        )

    def test_http_url(self):
        assert (
            extract_url_from_text("http://v.douyin.com/iRNBho5/") == "http://v.douyin.com/iRNBho5/"
        )

    def test_long_url_takes_priority(self):
        text = "https://www.douyin.com/video/7380123456789012345"
        assert extract_url_from_text(text) == "https://www.douyin.com/video/7380123456789012345"


# ===== detect_platform tests =====


class TestDetectPlatform:
    def test_douyin_share_link(self):
        assert detect_platform("https://v.douyin.com/iRNBho5/") == "douyin"

    def test_douyin_web_link(self):
        assert detect_platform("https://www.douyin.com/video/7380000000000000000") == "douyin"

    def test_unsupported_platform(self):
        assert detect_platform("https://www.bilibili.com/video/BV1xx411c7XY") is None

    def test_youtube_unsupported(self):
        assert detect_platform("https://youtube.com/watch?v=xxx") is None

    def test_garbage_input(self):
        assert detect_platform("not a url at all") is None


# ===== extract_douyin_id tests =====


class TestExtractDouyinId:
    def test_from_web_url(self):
        vid = extract_douyin_id("https://www.douyin.com/video/7380123456789012345")
        assert vid == "7380123456789012345"

    def test_short_id(self):
        assert extract_douyin_id("https://www.douyin.com/video/123") is None

    def test_no_video_path(self):
        assert extract_douyin_id("https://www.douyin.com/user/xxx") is None

    def test_from_redirected_url_with_query(self):
        url = "https://www.douyin.com/video/7380123456789012345?previous_page=web_code_link"
        assert extract_douyin_id(url) == "7380123456789012345"


class TestCanonicalWatchUrl:
    def test_rewrites_douyin_to_web_watch_url(self):
        info = VideoInfo("7380123456789012345", "douyin", "https://v.douyin.com/x/")
        assert canonical_watch_url(info) == "https://www.douyin.com/video/7380123456789012345"

    def test_keeps_non_douyin_url(self):
        info = VideoInfo("BV1xx", "bilibili", "https://b23.tv/xxx")
        assert canonical_watch_url(info) == "https://b23.tv/xxx"


# ===== resolve_url tests =====


class TestResolveUrl:
    def test_rejects_unsupported(self):
        with pytest.raises(UnsupportedPlatformError, match="仅支持抖音"):
            resolve_url("https://youtube.com/watch?v=xxx")

    @patch("vocap.url_resolver._follow_redirect")
    def test_resolves_short_link(self, mock_redirect):
        mock_redirect.return_value = (
            "https://www.douyin.com/video/7380123456789012345?previous_page=web_code_link"
        )
        info = resolve_url("https://v.douyin.com/iRNBho5/")
        assert info.video_id == "7380123456789012345"
        assert info.platform == "douyin"

    def test_resolves_long_link(self):
        info = resolve_url("https://www.douyin.com/video/7380123456789012345")
        assert info.video_id == "7380123456789012345"
        assert info.platform == "douyin"

    @patch("vocap.url_resolver._follow_redirect")
    def test_redirect_no_video_id(self, mock_redirect):
        mock_redirect.return_value = "https://www.douyin.com/login"
        with pytest.raises(URLParseError, match=r"无法.*提取视频 ID"):
            resolve_url("https://v.douyin.com/expired/")

    @patch("vocap.url_resolver._follow_redirect")
    def test_redirect_timeout(self, mock_redirect):
        mock_redirect.side_effect = httpx.TimeoutException("Connection timed out")
        with pytest.raises(URLResolveError, match=r"短链.*失败"):
            resolve_url("https://v.douyin.com/timeout/")
