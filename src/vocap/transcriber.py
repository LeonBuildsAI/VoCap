from __future__ import annotations

import warnings
from collections.abc import Callable

from vocap.errors import TranscriptionError
from vocap.models import Segment, Transcript

_MLX_DEFAULT = "mlx-community/whisper-large-v3-turbo"

_MLX_MODEL_MAP = {
    "tiny": "mlx-community/whisper-tiny",
    "base": "mlx-community/whisper-base",
    "small": "mlx-community/whisper-small",
    "medium": "mlx-community/whisper-medium",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": _MLX_DEFAULT,
}

_INITIAL_PROMPTS: dict[str, str] = {
    "zh": "以下是普通话的句子。这是一段口播视频的文案，内容涵盖了各种话题。",
}


def _get_initial_prompt(language: str) -> str | None:
    """根据语言返回 Whisper initial_prompt 风格引导文本。

    中文场景下返回包含简体中文标点的示范文本，引导 Whisper 在转写中输出标点。
    其他语言返回 None（Whisper 对英文等语言默认会输出标点）。
    """
    return _INITIAL_PROMPTS.get(language)


def get_default_model() -> str:
    return _MLX_DEFAULT


def resolve_model_name(model_size: str) -> str:
    """将模型简称解析为完整的 HuggingFace repo 名称。"""
    if not model_size:
        return _MLX_DEFAULT
    if "/" in model_size:
        return model_size
    repo = _MLX_MODEL_MAP.get(model_size)
    if repo is None:
        warnings.warn(
            f"未知模型简称 '{model_size}'，将使用默认模型 {_MLX_DEFAULT}",
            stacklevel=2,
        )
        return _MLX_DEFAULT
    return repo


def _get_mlx_whisper():
    """延迟导入 mlx_whisper，支持 mock 和非 Apple Silicon 环境。"""
    try:
        import mlx_whisper

        return mlx_whisper
    except ImportError as e:
        raise TranscriptionError(
            "mlx-whisper 未安装或当前平台不支持。"
            "本工具仅支持 macOS Apple Silicon (M1/M2/M3/M4/M5)。\n"
            "安装: pip install mlx-whisper"
        ) from e


def transcribe(
    audio_path: str,
    model_size: str = "",
    language: str = "zh",
    on_progress: Callable[[str], None] | None = None,
) -> Transcript:
    """将音频文件转写为文本。

    Args:
        audio_path: WAV 音频文件路径
        model_size: 模型简称或完整 HuggingFace repo 名称
        language: 语言代码
        on_progress: 进度回调

    Returns:
        Transcript 对象

    Raises:
        TranscriptionError: 转写失败
    """
    mlx_whisper = _get_mlx_whisper()
    repo = resolve_model_name(model_size)

    if on_progress:
        on_progress(f"开始语音识别 (mlx-whisper: {repo.split('/')[-1]})...")

    try:
        result = mlx_whisper.transcribe(
            audio_path,
            path_or_hf_repo=repo,
            language=language,
            initial_prompt=_get_initial_prompt(language),
            condition_on_previous_text=True,
            word_timestamps=False,
        )
    except Exception as e:
        raise TranscriptionError(f"语音识别失败: {e}") from e

    segments: list[Segment] = []
    texts: list[str] = []
    for seg in result.get("segments", []):
        text = seg["text"].strip()
        if not text:
            continue
        segments.append(Segment(start=seg["start"], end=seg["end"], text=text))
        texts.append(text)

    if on_progress:
        on_progress("识别完成")

    duration = segments[-1].end if segments else 0.0

    return Transcript(
        text="".join(texts),
        segments=segments,
        language=result.get("language", language),
        duration=duration,
    )
