from __future__ import annotations

import json
from datetime import datetime

from vocap.models import Transcript, VideoInfo


def to_result_dict(info: VideoInfo, transcript: Transcript, elapsed_seconds: float = 0.0) -> dict:
    """将结果转为字典，单条和批量 JSON 共用此结构。"""
    data = info.to_dict()
    data["transcript"] = transcript.to_dict()
    data["elapsed_seconds"] = elapsed_seconds
    data["extracted_at"] = datetime.now().isoformat()
    return data


def to_json(info: VideoInfo, transcript: Transcript) -> str:
    """输出 JSON 格式。"""
    return json.dumps(to_result_dict(info, transcript), ensure_ascii=False, indent=2)


def to_markdown(info: VideoInfo, transcript: Transcript) -> str:
    """输出 Markdown 格式。"""
    lines = [
        "# 视频文案",
        "",
        f"- **视频 ID**: {info.video_id}",
        f"- **平台**: {info.platform}",
        f"- **链接**: {info.url}",
        f"- **提取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
        "## 文案",
        "",
        transcript.text,
        "",
    ]
    return "\n".join(lines)


def to_srt(info: VideoInfo, transcript: Transcript) -> str:
    """输出 SRT 字幕格式。"""
    lines: list[str] = []
    for i, seg in enumerate(transcript.segments, 1):
        lines.append(str(i))
        lines.append(f"{_fmt_srt_time(seg.start)} --> {_fmt_srt_time(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)


def to_txt(info: VideoInfo, transcript: Transcript) -> str:
    """输出纯文本。"""
    return transcript.text


def format_results(results: list[tuple[VideoInfo, Transcript, float]], fmt: str) -> str:
    """格式化一个或多个提取结果。

    JSON 格式：单条直接输出对象，多条输出数组。
    其他格式：多条用分隔线连接。
    """
    if fmt in ("json",):
        data = [to_result_dict(info, t, elapsed) for info, t, elapsed in results]
        payload = data[0] if len(data) == 1 else data
        return json.dumps(payload, ensure_ascii=False, indent=2)

    if len(results) == 1:
        info, transcript, _ = results[0]
        return format_output(info, transcript, fmt)

    parts = [format_output(info, t, fmt) for info, t, _ in results]
    return "\n\n---\n\n".join(parts)


def format_output(info: VideoInfo, transcript: Transcript, fmt: str) -> str:
    """根据格式名输出对应格式的字符串。

    Raises:
        ValueError: 不支持的格式
    """
    formatters = {
        "json": to_json,
        "markdown": to_markdown,
        "md": to_markdown,
        "srt": to_srt,
        "txt": to_txt,
        "text": to_txt,
    }
    fn = formatters.get(fmt.lower())
    if fn is None:
        valid = ", ".join(sorted(formatters))
        raise ValueError(f"不支持的格式: {fmt}（可选: {valid}）")
    return fn(info, transcript)


def _fmt_srt_time(seconds: float) -> str:
    """将秒数格式化为 SRT 时间戳 HH:MM:SS,mmm。"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
