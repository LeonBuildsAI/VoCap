from __future__ import annotations

import re

import httpx

from vocap.errors import UnsupportedPlatformError, URLParseError, URLResolveError
from vocap.models import VideoInfo

_DOUYIN_DOMAINS_RE = re.compile(r"https?://(v\.douyin\.com|www\.douyin\.com)")
_DOUYIN_VID_RE = re.compile(r"/video/(\d{15,25})")

_DOUYIN_SHARE_URL_RE = re.compile(r"https?://v\.douyin\.com/[A-Za-z0-9_-]+/?")
_DOUYIN_WEB_URL_RE = re.compile(r"https?://www\.douyin\.com/video/\d+")

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def extract_url_from_text(text: str) -> str | None:
    """从抖音分享文本中提取纯 URL。

    优先匹配长链(包含更多信息), 其次短链。
    如果找不到任何抖音链接返回 None。
    """
    if not text:
        return None
    m = _DOUYIN_WEB_URL_RE.search(text)
    if m:
        return m.group(0)
    m = _DOUYIN_SHARE_URL_RE.search(text)
    if m:
        return m.group(0)
    return None


def detect_platform(url: str) -> str | None:
    """识别 URL 所属平台, 当前仅支持抖音。"""
    if _DOUYIN_DOMAINS_RE.search(url):
        return "douyin"
    return None


def extract_douyin_id(url: str) -> str | None:
    """从 URL 中用正则提取 15-25 位的抖音 video_id。"""
    m = _DOUYIN_VID_RE.search(url)
    return m.group(1) if m else None


def _follow_redirect(url: str) -> str:
    """跟随 HTTP 302 重定向, 返回最终 URL。"""
    with httpx.Client(headers={"User-Agent": _UA}, follow_redirects=True, timeout=10) as client:
        resp = client.get(url)
        return str(resp.url)


def _resolve_douyin(url: str) -> VideoInfo:
    """解析抖音链接, 返回 VideoInfo。"""
    vid = extract_douyin_id(url)

    if not vid:
        try:
            real_url = _follow_redirect(url)
        except httpx.HTTPError as e:
            raise URLResolveError(f"短链重定向失败: {e}") from e
        vid = extract_douyin_id(real_url)

    if not vid:
        raise URLParseError(f"无法从链接中提取视频 ID: {url}")

    return VideoInfo(
        video_id=vid,
        platform="douyin",
        url=url,
    )


def canonical_watch_url(info: VideoInfo) -> str:
    """把已解析的视频信息转成 yt-dlp 能识别的观看页 URL。"""
    if info.platform == "douyin" and info.video_id:
        return f"https://www.douyin.com/video/{info.video_id}"
    return info.url


def resolve_url(url: str) -> VideoInfo:
    """解析视频 URL, 返回 VideoInfo。

    Raises:
        UnsupportedPlatformError: URL 不属于已支持的平台
        URLParseError: URL 格式无法解析
        URLResolveError: 短链重定向失败
    """
    platform = detect_platform(url)
    if platform == "douyin":
        return _resolve_douyin(url)
    raise UnsupportedPlatformError(f"不支持的链接: {url} (当前仅支持抖音)")
