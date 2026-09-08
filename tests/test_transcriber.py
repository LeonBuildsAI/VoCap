from unittest.mock import MagicMock, patch

import pytest

from vocap.models import Transcript
from vocap.transcriber import (
    _INITIAL_PROMPTS,
    _get_initial_prompt,
    get_default_model,
    resolve_model_name,
    transcribe,
)


class TestModelResolution:
    def test_default_model(self):
        assert get_default_model() == "mlx-community/whisper-large-v3-turbo"

    def test_resolve_shorthand_tiny(self):
        assert resolve_model_name("tiny") == "mlx-community/whisper-tiny"

    def test_resolve_shorthand_large_v3_turbo(self):
        assert resolve_model_name("large-v3-turbo") == "mlx-community/whisper-large-v3-turbo"

    def test_resolve_full_repo_name(self):
        repo = "mlx-community/whisper-large-v3-turbo-4bit"
        assert resolve_model_name(repo) == repo

    def test_unknown_model_falls_back_with_warning(self):
        with pytest.warns(UserWarning, match="未知模型简称"):
            result = resolve_model_name("nonexistent")
        assert result == get_default_model()

    def test_resolve_empty_string(self):
        assert resolve_model_name("") == get_default_model()


class TestTranscribe:
    @patch("vocap.transcriber._get_mlx_whisper")
    def test_basic_transcription(self, mock_get_mlx):
        mock_mlx = MagicMock()
        mock_get_mlx.return_value = mock_mlx
        mock_mlx.transcribe.return_value = {
            "text": "你好世界",
            "segments": [
                {"start": 0.0, "end": 2.0, "text": " 你好世界"},
            ],
            "language": "zh",
        }
        result = transcribe("/fake/audio.wav")
        assert isinstance(result, Transcript)
        assert result.text == "你好世界"
        assert len(result.segments) == 1
        assert result.segments[0].text == "你好世界"

    @patch("vocap.transcriber._get_mlx_whisper")
    def test_silent_audio(self, mock_get_mlx):
        mock_mlx = MagicMock()
        mock_get_mlx.return_value = mock_mlx
        mock_mlx.transcribe.return_value = {
            "text": "",
            "segments": [],
            "language": "zh",
        }
        result = transcribe("/fake/silent.wav")
        assert result.text == ""
        assert result.segments == []
        assert result.duration == 0.0

    @patch("vocap.transcriber._get_mlx_whisper")
    def test_strips_segment_text(self, mock_get_mlx):
        mock_mlx = MagicMock()
        mock_get_mlx.return_value = mock_mlx
        mock_mlx.transcribe.return_value = {
            "text": "  你好  ",
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "  你好  "},
            ],
            "language": "zh",
        }
        result = transcribe("/fake/audio.wav")
        assert result.segments[0].text == "你好"

    @patch("vocap.transcriber._get_mlx_whisper")
    def test_skips_empty_segments(self, mock_get_mlx):
        mock_mlx = MagicMock()
        mock_get_mlx.return_value = mock_mlx
        mock_mlx.transcribe.return_value = {
            "text": "你好",
            "segments": [
                {"start": 0.0, "end": 0.5, "text": "   "},
                {"start": 0.5, "end": 1.5, "text": "你好"},
            ],
            "language": "zh",
        }
        result = transcribe("/fake/audio.wav")
        assert len(result.segments) == 1

    @patch("vocap.transcriber._get_mlx_whisper")
    def test_progress_callback(self, mock_get_mlx):
        mock_mlx = MagicMock()
        mock_get_mlx.return_value = mock_mlx
        mock_mlx.transcribe.return_value = {
            "text": "OK",
            "segments": [{"start": 0.0, "end": 1.0, "text": "OK"}],
            "language": "zh",
        }
        messages = []
        transcribe("/fake/audio.wav", on_progress=messages.append)
        assert any("语音识别" in m for m in messages)
        assert any("识别完成" in m for m in messages)

    @patch("vocap.transcriber._get_mlx_whisper")
    def test_wraps_exception_as_transcription_error(self, mock_get_mlx):
        mock_mlx = MagicMock()
        mock_get_mlx.return_value = mock_mlx
        mock_mlx.transcribe.side_effect = RuntimeError("GPU out of memory")

        from vocap.errors import TranscriptionError

        with pytest.raises(TranscriptionError, match="语音识别失败"):
            transcribe("/fake/audio.wav")


class TestInitialPrompt:
    def test_chinese_returns_expected_prompt(self):
        result = _get_initial_prompt("zh")
        assert result == _INITIAL_PROMPTS["zh"]
        assert "。" in result and "，" in result

    @pytest.mark.parametrize("language", ["en", "xx", ""])
    def test_unsupported_language_returns_none(self, language):
        assert _get_initial_prompt(language) is None


class TestTranscribeParameters:
    """验证 transcribe() 传给 mlx_whisper.transcribe() 的关键参数。"""

    @patch("vocap.transcriber._get_mlx_whisper")
    def test_chinese_passes_prompt_and_context(self, mock_get_mlx):
        mock_mlx = MagicMock()
        mock_get_mlx.return_value = mock_mlx
        mock_mlx.transcribe.return_value = {
            "text": "你好",
            "segments": [{"start": 0.0, "end": 1.0, "text": "你好"}],
            "language": "zh",
        }

        transcribe("/fake/audio.wav", language="zh")

        call_kwargs = mock_mlx.transcribe.call_args.kwargs
        assert call_kwargs["initial_prompt"] == _INITIAL_PROMPTS["zh"]
        assert call_kwargs["condition_on_previous_text"] is True

    @patch("vocap.transcriber._get_mlx_whisper")
    def test_english_passes_no_prompt(self, mock_get_mlx):
        mock_mlx = MagicMock()
        mock_get_mlx.return_value = mock_mlx
        mock_mlx.transcribe.return_value = {
            "text": "hello",
            "segments": [{"start": 0.0, "end": 1.0, "text": "hello"}],
            "language": "en",
        }

        transcribe("/fake/audio.wav", language="en")

        call_kwargs = mock_mlx.transcribe.call_args.kwargs
        assert call_kwargs["initial_prompt"] is None
