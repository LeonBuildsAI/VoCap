from __future__ import annotations

import re

from vocap.models import Segment, Transcript


def clean_text(text: str) -> str:
    """清洗 ASR 转写文本。

    规则:
    1. 合并多余空白字符为单个空格
    2. 去除中文标点前的空格
    3. 去除三次及以上的重复片段（模式长度 >= 3 字符）
    """
    if not text or not text.strip():
        return ""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([，。！？、；：])", r"\1", text)
    for length in range(6, 2, -1):
        pattern = re.compile(r"(.{" + str(length) + r",}?)\1{2,}")
        text = pattern.sub(r"\1", text)
    return text.strip()


def clean_transcript(transcript: Transcript) -> Transcript:
    """清洗 Transcript 的文本和 segments 内容。"""
    cleaned_segments = [
        Segment(seg.start, seg.end, clean_text(seg.text)) for seg in transcript.segments
    ]
    return Transcript(
        text=clean_text(transcript.text),
        segments=cleaned_segments,
        language=transcript.language,
        duration=transcript.duration,
    )
