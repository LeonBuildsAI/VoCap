import pytest

from vocap.models import Segment, Transcript, VideoInfo


@pytest.fixture
def sample_segments():
    return [
        Segment(start=0.0, end=3.0, text="你好世界。"),
        Segment(start=3.0, end=6.0, text="这是测试。"),
    ]


@pytest.fixture
def sample_transcript(sample_segments):
    return Transcript(
        text="你好世界。这是测试。",
        segments=sample_segments,
        language="zh",
        duration=6.0,
    )


@pytest.fixture
def sample_video_info():
    return VideoInfo(
        video_id="7380123456789012345",
        platform="douyin",
        url="https://v.douyin.com/test/",
    )
