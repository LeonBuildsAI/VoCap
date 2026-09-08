from __future__ import annotations

import sys
import time
from collections.abc import Callable

from vocap.cleaner import clean_transcript
from vocap.downloader import cleanup, download_audio
from vocap.errors import AudioDownloadError
from vocap.models import Transcript, VideoInfo
from vocap.transcriber import transcribe
from vocap.url_resolver import canonical_watch_url, resolve_url

_TRANSIENT_MARKERS = ("HTTP Error 403", "Fresh cookies")


def is_transient_download_error(exc: BaseException) -> bool:
    """抖音详情接口 403/限流时 yt-dlp 给出的可重试错误。"""
    if not isinstance(exc, AudioDownloadError):
        return False
    text = str(exc)
    return any(marker in text for marker in _TRANSIENT_MARKERS)


def extract(
    url: str,
    model_size: str = "",
    on_status: Callable[[str], None] | None = None,
    cookies_from_browser: str = "",
    cookiefile: str = "",
    download_retries: int = 3,
) -> tuple[VideoInfo, Transcript, float]:
    """执行完整的提取流程: URL -> 下载 -> 转写 -> 清洗。

    Returns:
        (VideoInfo, Transcript, elapsed_seconds) 元组
    """
    t0 = time.monotonic()

    def status(msg: str) -> None:
        if on_status:
            on_status(msg)
        else:
            print(f"  → {msg}", file=sys.stderr)

    status("解析链接...")
    info = resolve_url(url)
    status(f"平台: {info.platform} | {info.video_id}")

    status("下载音频...")
    audio_path = None
    attempts = max(download_retries, 0) + 1
    for attempt in range(attempts):
        try:
            audio_path = download_audio(
                canonical_watch_url(info),
                on_progress=status,
                cookies_from_browser=cookies_from_browser,
                cookiefile=cookiefile,
            )
            break
        except AudioDownloadError as e:
            if not is_transient_download_error(e) or attempt >= attempts - 1:
                raise
            wait = 2 ** (attempt + 1)
            status(f"下载被限流，{wait}s 后重试 ({attempt + 1}/{download_retries})...")
            time.sleep(wait)

    if audio_path is None:
        raise AudioDownloadError("下载失败：未生成音频文件")

    try:
        transcript = transcribe(audio_path, model_size=model_size, on_progress=status)
        status("文本清洗...")
        cleaned = clean_transcript(transcript)
    finally:
        cleanup(audio_path)

    elapsed = round(time.monotonic() - t0, 2)
    status(f"完成 ✓ ({elapsed}s)")
    return info, cleaned, elapsed
