# tests/test_models.py
from vocap.models import Segment, Transcript, VideoInfo


class TestSegment:
    def test_duration(self):
        seg = Segment(start=1.0, end=4.5, text="测试")
        assert seg.duration == 3.5

    def test_zero_duration(self):
        seg = Segment(start=2.0, end=2.0, text="瞬间")
        assert seg.duration == 0.0

    def test_to_dict(self):
        seg = Segment(start=0.0, end=1.0, text="你好")
        d = seg.to_dict()
        assert d == {"start": 0.0, "end": 1.0, "text": "你好"}


class TestTranscript:
    def test_basic(self):
        t = Transcript(
            text="第一句。第二句。",
            segments=[
                Segment(0.0, 3.0, "第一句。"),
                Segment(3.0, 6.0, "第二句。"),
            ],
            language="zh",
            duration=6.0,
        )
        assert len(t.segments) == 2
        assert t.duration == 6.0

    def test_empty_segments(self):
        t = Transcript(text="", segments=[], language="zh", duration=0.0)
        assert t.segments == []
        assert t.text == ""

    def test_to_dict(self):
        t = Transcript(
            text="你好",
            segments=[Segment(0.0, 1.0, "你好")],
            language="zh",
            duration=1.0,
        )
        d = t.to_dict()
        assert d["text"] == "你好"
        assert d["segments"] == [{"start": 0.0, "end": 1.0, "text": "你好"}]
        assert d["language"] == "zh"


class TestVideoInfo:
    def test_to_dict(self):
        info = VideoInfo(
            video_id="123",
            platform="douyin",
            url="https://v.douyin.com/x",
        )
        d = info.to_dict()
        assert d == {
            "video_id": "123",
            "platform": "douyin",
            "url": "https://v.douyin.com/x",
        }

    def test_only_three_fields(self):
        info = VideoInfo("1", "douyin", "u")
        d = info.to_dict()
        assert set(d.keys()) == {"video_id", "platform", "url"}
