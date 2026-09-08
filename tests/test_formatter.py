import json

import pytest

from vocap.formatter import (
    format_output,
    format_results,
    to_json,
    to_markdown,
    to_result_dict,
    to_srt,
    to_txt,
)
from vocap.models import Segment, Transcript, VideoInfo


class TestToResultDict:
    def test_contains_all_fields(self, sample_video_info, sample_transcript):
        data = to_result_dict(sample_video_info, sample_transcript, elapsed_seconds=5.23)
        assert data["video_id"] == "7380123456789012345"
        assert data["transcript"]["text"] == "你好世界。这是测试。"
        assert data["elapsed_seconds"] == 5.23
        assert "extracted_at" in data

    def test_default_elapsed_is_zero(self, sample_video_info, sample_transcript):
        data = to_result_dict(sample_video_info, sample_transcript)
        assert data["elapsed_seconds"] == 0.0

    def test_no_unused_fields(self, sample_video_info, sample_transcript):
        data = to_result_dict(sample_video_info, sample_transcript)
        assert "title" not in data
        assert "author" not in data
        assert "thumbnail" not in data

    def test_batch_and_single_share_structure(self, sample_video_info, sample_transcript):
        from_dict = to_result_dict(sample_video_info, sample_transcript)
        from_json = json.loads(to_json(sample_video_info, sample_transcript))
        assert set(from_dict.keys()) == set(from_json.keys())

    def test_contains_segments(self, sample_video_info, sample_transcript):
        data = to_result_dict(sample_video_info, sample_transcript)
        assert "segments" in data["transcript"]
        assert len(data["transcript"]["segments"]) == 2
        assert data["transcript"]["segments"][0]["text"] == "你好世界。"


class TestToJson:
    def test_basic_structure(self, sample_video_info, sample_transcript):
        output = to_json(sample_video_info, sample_transcript)
        data = json.loads(output)
        assert data["video_id"] == "7380123456789012345"
        assert data["transcript"]["text"] == "你好世界。这是测试。"
        assert len(data["transcript"]["segments"]) == 2
        assert "elapsed_seconds" in data
        assert "extracted_at" in data

    def test_json_is_valid_utf8(self, sample_video_info, sample_transcript):
        output = to_json(sample_video_info, sample_transcript)
        assert "\\u" not in output


class TestToMarkdown:
    def test_basic_structure(self, sample_video_info, sample_transcript):
        output = to_markdown(sample_video_info, sample_transcript)
        assert "# 视频文案" in output
        assert "7380123456789012345" in output
        assert "你好世界" in output
        assert "douyin" in output

    def test_no_unused_metadata(self, sample_video_info, sample_transcript):
        output = to_markdown(sample_video_info, sample_transcript)
        assert "未知标题" not in output
        assert "未知" not in output.split("平台")[0]


class TestToSrt:
    def test_basic_structure(self, sample_video_info, sample_transcript):
        output = to_srt(sample_video_info, sample_transcript)
        assert "1\n" in output
        assert "00:00:00,000 --> 00:00:03,000" in output
        assert "你好世界。" in output
        assert "2\n" in output

    def test_zero_duration_segment(self):
        info = VideoInfo("1", "douyin", "u")
        t = Transcript(
            text="瞬间",
            segments=[Segment(0.0, 0.0, "瞬间")],
            language="zh",
            duration=0.0,
        )
        output = to_srt(info, t)
        assert "00:00:00,000 --> 00:00:00,000" in output

    def test_hour_boundary(self):
        info = VideoInfo("1", "douyin", "u")
        t = Transcript(
            text="长视频",
            segments=[Segment(3661.5, 3665.0, "长视频")],
            language="zh",
            duration=3665.0,
        )
        output = to_srt(info, t)
        assert "01:01:01,500" in output


class TestToTxt:
    def test_basic(self, sample_video_info, sample_transcript):
        assert to_txt(sample_video_info, sample_transcript) == "你好世界。这是测试。"


class TestFormatOutput:
    def test_json_format(self, sample_video_info, sample_transcript):
        output = format_output(sample_video_info, sample_transcript, "json")
        assert json.loads(output)

    def test_markdown_format(self, sample_video_info, sample_transcript):
        output = format_output(sample_video_info, sample_transcript, "markdown")
        assert "# " in output

    def test_md_alias(self, sample_video_info, sample_transcript):
        output = format_output(sample_video_info, sample_transcript, "md")
        assert "# " in output

    def test_srt_format(self, sample_video_info, sample_transcript):
        output = format_output(sample_video_info, sample_transcript, "srt")
        assert "-->" in output

    def test_txt_format(self, sample_video_info, sample_transcript):
        output = format_output(sample_video_info, sample_transcript, "txt")
        assert "你好世界" in output

    def test_unsupported_format(self, sample_video_info, sample_transcript):
        with pytest.raises(ValueError, match="不支持的格式"):
            format_output(sample_video_info, sample_transcript, "pdf")


class TestFormatResults:
    def test_single_json(self, sample_video_info, sample_transcript):
        output = format_results([(sample_video_info, sample_transcript, 1.5)], "json")
        data = json.loads(output)
        assert isinstance(data, dict)
        assert data["elapsed_seconds"] == 1.5

    def test_batch_json(self, sample_video_info, sample_transcript):
        pair = (sample_video_info, sample_transcript)
        output = format_results(
            [(*pair, 1.0), (*pair, 2.0)],
            "json",
        )
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_single_markdown(self, sample_video_info, sample_transcript):
        output = format_results([(sample_video_info, sample_transcript, 0.0)], "markdown")
        assert "# 视频文案" in output

    def test_batch_srt_joined(self, sample_video_info, sample_transcript):
        pair = (sample_video_info, sample_transcript)
        output = format_results(
            [(*pair, 0.0), (*pair, 0.0)],
            "srt",
        )
        assert output.count("---") == 1
