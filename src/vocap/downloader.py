from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable

import yt_dlp  # type: ignore[import-untyped]

from vocap.errors import AudioDownloadError, DownloadError, FFmpegNotFoundError

_AUDIO_EXTENSIONS = [".webm", ".m4a", ".mp3", ".wav", ".opus", ".ogg", ".mp4", ".aac"]
_BROWSER_SPEC_RE = re.compile(
    r"""(?x)
    (?P<name>[^+:]+)
    (?:\s*\+\s*(?P<keyring>[^:]+))?
    (?:\s*:\s*(?!:)(?P<profile>.+?))?
    (?:\s*::\s*(?P<container>.+))?
    """
)


def parse_cookies_from_browser(spec: str) -> tuple[str, str | None, str | None, str | None]:
    """解析 yt-dlp 的 BROWSER[+KEYRING][:PROFILE][::CONTAINER] 语法。"""
    spec = spec.strip()
    m = _BROWSER_SPEC_RE.fullmatch(spec)
    if not m:
        raise AudioDownloadError(f"无效的浏览器 cookie 参数: {spec}")
    name, keyring, profile, container = m.group("name", "keyring", "profile", "container")
    return (name.lower(), profile, keyring.upper() if keyring else None, container)


def check_ffmpeg(path: str = "ffmpeg") -> bool:
    """检查 ffmpeg 是否可用。"""
    return shutil.which(path) is not None


def require_ffmpeg(path: str = "ffmpeg") -> None:
    """确保 ffmpeg 可用，否则抛出异常。"""
    if not check_ffmpeg(path):
        raise FFmpegNotFoundError(
            "未找到 ffmpeg,请先安装:\n"
            "  macOS: brew install ffmpeg\n"
            "  详见: https://ffmpeg.org/download.html"
        )


def _find_downloaded_file(expected_path: str) -> str | None:
    """查找 yt-dlp 实际下载的文件（扩展名可能与预期不同）。"""
    if os.path.exists(expected_path):
        return expected_path
    base, _ = os.path.splitext(expected_path)
    for ext in _AUDIO_EXTENSIONS:
        candidate = base + ext
        if os.path.exists(candidate):
            return candidate
    return None


def download_audio(
    url: str,
    ffmpeg_path: str = "ffmpeg",
    on_progress: Callable[[str], None] | None = None,
    cookies_from_browser: str = "",
    cookiefile: str = "",
) -> str:
    """下载视频音频轨并转换为 16kHz WAV。

    Returns:
        WAV 文件的绝对路径（位于系统临时目录）

    Raises:
        FFmpegNotFoundError: ffmpeg 未安装
        AudioDownloadError: yt-dlp 下载失败
        DownloadError: ffmpeg 转换失败
    """
    require_ffmpeg(ffmpeg_path)

    tmpdir = tempfile.mkdtemp(prefix="vocap_")
    try:
        raw_path = _download_with_ytdlp(
            url,
            tmpdir,
            on_progress,
            cookies_from_browser=cookies_from_browser,
            cookiefile=cookiefile,
        )
        wav_path = os.path.join(tmpdir, "audio_16k.wav")
        _convert_to_wav16k(raw_path, wav_path, ffmpeg_path)
        return wav_path
    except (AudioDownloadError, DownloadError):
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise AudioDownloadError(f"下载失败: {e}") from e


def _download_with_ytdlp(
    url: str,
    output_dir: str,
    on_progress: Callable[[str], None] | None = None,
    cookies_from_browser: str = "",
    cookiefile: str = "",
) -> str:
    """使用 yt-dlp 下载最佳音频轨道。"""
    opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        # 增加应对网络波动的韧性配置
        "retries": 10,  # 下载失败最多重试 10 次
        "fragment_retries": 10,  # 分片下载失败最多重试 10 次
        "http_chunk_size": 1048576,  # 强制按 1MB 分块下载，避免长时间长连接被掐断
    }
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = parse_cookies_from_browser(cookies_from_browser)
    if cookiefile:
        opts["cookiefile"] = cookiefile

    if on_progress:

        def hook(d: dict) -> None:
            if d["status"] == "downloading":
                pct = d.get("_percent_str", "?%").strip()
                on_progress(f"下载中 {pct}")
            elif d["status"] == "finished":
                on_progress("下载完成，正在转换格式...")

        opts["progress_hooks"] = [hook]

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise AudioDownloadError(f"yt-dlp 无法获取视频信息: {url}")
            filename = ydl.prepare_filename(info)
    except yt_dlp.utils.DownloadError as e:
        raise AudioDownloadError(
            f"音频下载失败: {e}\n提示: 尝试运行 pip install -U yt-dlp 更新 yt-dlp"
        ) from e

    result = _find_downloaded_file(filename)
    if result is None:
        raise AudioDownloadError(f"下载完成但找不到输出文件，目录: {output_dir}")
    return result


def _convert_to_wav16k(input_path: str, output_path: str, ffmpeg_path: str) -> None:
    """使用 ffmpeg 将音频转换为 16kHz 单声道 WAV。"""
    cmd = [
        ffmpeg_path,
        "-i",
        input_path,
        "-ar",
        "16000",
        "-ac",
        "1",
        "-f",
        "wav",
        "-y",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        raise DownloadError(f"ffmpeg 音频转换失败: {stderr[:500]}")


def cleanup(audio_path: str) -> None:
    """清理临时目录。仅删除 vocap_ 前缀的临时目录，防止误删。"""
    parent = os.path.dirname(audio_path)
    if parent and os.path.basename(parent).startswith("vocap_"):
        shutil.rmtree(parent, ignore_errors=True)
