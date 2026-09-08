from __future__ import annotations


class VoCapError(Exception):
    """vocap 所有异常的基类"""


class URLError(VoCapError):
    """URL 解析相关错误的基类"""


class UnsupportedPlatformError(URLError):
    """URL 属于不支持的平台"""


class URLParseError(URLError):
    """URL 格式无法解析（如找不到 video_id）"""


class URLResolveError(URLError):
    """URL 短链重定向失败（网络问题、链接过期等）"""


class DownloadError(VoCapError):
    """音频下载相关错误的基类"""


class FFmpegNotFoundError(DownloadError):
    """系统未安装 ffmpeg 或 ffmpeg 不在 PATH 中"""


class AudioDownloadError(DownloadError):
    """yt-dlp 下载音频失败"""


class TranscriptionError(VoCapError):
    """ASR 转写相关错误的基类"""
