from vocap.cleaner import clean_text, clean_transcript
from vocap.models import Segment, Transcript


class TestCleanText:
    def test_empty_string(self):
        assert clean_text("") == ""

    def test_only_whitespace(self):
        assert clean_text("   \t\n  ") == ""

    def test_space_before_chinese_punct(self):
        assert clean_text("你好 ，世界 。") == "你好，世界。"

    def test_multiple_punctuations(self):
        assert clean_text("真的 ！你说 ？对 ；没错 ：好") == "真的！你说？对；没错：好"

    def test_extra_whitespace(self):
        assert clean_text("你好   世界  ！") == "你好 世界！"

    def test_triple_repetition(self):
        result = clean_text("这很重要这很重要这很重要然后")
        assert result.count("这很重要") == 1
        assert "然后" in result

    def test_four_times_repetition(self):
        result = clean_text("好的好的好的好的好的好的好的好的好的然后")
        assert result.count("好的好的好的") <= 1

    def test_no_repetition(self):
        text = "第一句话。第二句话。第三句话。"
        assert clean_text(text) == text

    def test_normal_text_unchanged(self):
        text = "大家好，今天我们来聊一聊。"
        assert clean_text(text) == text

    def test_mixed_chinese_english(self):
        assert clean_text("Hello 你好 ，World") == "Hello 你好，World"

    def test_emoji_preserved(self):
        assert "🔥" in clean_text("太棒了🔥")

    def test_combined_issues(self):
        text = "你好   ，这很重要这很重要这很重要  ！"
        result = clean_text(text)
        assert "   " not in result
        assert " ，" not in result
        assert result.count("这很重要") == 1


class TestCleanTranscript:
    def test_cleans_transcript_text(self):
        t = Transcript(
            text="你好 ，世界  。",
            segments=[Segment(0.0, 3.0, "你好 ，世界  。")],
            language="zh",
            duration=3.0,
        )
        cleaned = clean_transcript(t)
        assert cleaned.text == "你好，世界。"
        assert cleaned.segments[0].text == "你好，世界。"
        assert cleaned.language == "zh"
        assert cleaned.duration == 3.0

    def test_cleans_segment_text(self):
        t = Transcript(
            text="你好 ，世界  。",
            segments=[
                Segment(0.0, 1.5, "你好 ，"),
                Segment(1.5, 3.0, "世界  。"),
            ],
            language="zh",
            duration=3.0,
        )
        cleaned = clean_transcript(t)
        assert cleaned.segments[0].text == "你好，"
        assert cleaned.segments[1].text == "世界。"
