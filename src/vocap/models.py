from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Segment:
    start: float
    end: float
    text: str

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end, "text": self.text}


@dataclass
class Transcript:
    text: str
    segments: list[Segment]
    language: str
    duration: float

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "segments": [seg.to_dict() for seg in self.segments],
            "language": self.language,
            "duration": self.duration,
        }


@dataclass
class VideoInfo:
    video_id: str
    platform: str
    url: str

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "platform": self.platform,
            "url": self.url,
        }
