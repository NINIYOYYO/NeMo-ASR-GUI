"""字幕格式生成与解析服务模块。

支持标准 SRT、WebVTT、纯文本 TXT、JSON、歌词 LRC、ASS 以及逐词/逐字级字幕生成与解析。
"""

import json
import re
from typing import Any

from core.constants import (
    CENTISECONDS_PER_SECOND,
    MS_PER_HOUR,
    MS_PER_MINUTE,
    MS_PER_SECOND,
    SECONDS_PER_HOUR,
    SECONDS_PER_MINUTE,
    SubtitleFormat,
)
from interfaces import ISubtitleGenerator, SubtitleSegmentDict


class SubtitleService(ISubtitleGenerator):
    """生成多种格式字幕文件内容的服务。

    支持格式: SRT, VTT, TXT, JSON, LRC, ASS, WORD_SRT, CHAR_SRT
    """

    def generate_content(
        self,
        segment_timestamps: list[SubtitleSegmentDict] | list[dict[str, Any]],
        format_type: str | SubtitleFormat,
    ) -> str:
        """根据时间戳列表生成指定格式的字幕内容。

        Args:
            segment_timestamps (list[SubtitleSegmentDict] | list[dict[str, Any]]): 包含 start, end, segment 等字段的字典列表。
            format_type (str | SubtitleFormat): 格式类型 (例如 'srt', 'vtt', 'txt', 'json', 'lrc', 'ass')。

        Returns:
            str: 格式化后的字幕文本字符串。

        Raises:
            ValueError: 当请求不支持的字幕格式时抛出。
        """
        fmt_str = format_type.value if isinstance(format_type, SubtitleFormat) else str(format_type)
        method_name = f"_generate_{fmt_str.lower()}"
        if hasattr(self, method_name):
            return getattr(self, method_name)(segment_timestamps)
        raise ValueError(f"不支持的字幕格式: {format_type}")

    def format_time(self, seconds: float, separator: str = ",") -> str:
        """格式化时间为 HH:MM:SS,mmm (SRT) 或 HH:MM:SS.mmm (VTT)。

        先整体四舍五入到毫秒再拆分，避免浮点截断误差。

        Args:
            seconds (float): 时间秒数。
            separator (str): 秒与毫秒之间的分隔符，默认为逗号。

        Returns:
            str: 格式化后的时间字符串。
        """
        if seconds < 0:
            seconds = 0.0
        total_ms = int(round(seconds * MS_PER_SECOND))
        hours, rem = divmod(total_ms, MS_PER_HOUR)
        minutes, rem = divmod(rem, MS_PER_MINUTE)
        secs, milliseconds = divmod(rem, MS_PER_SECOND)
        return f"{hours:02}:{minutes:02}:{secs:02}{separator}{milliseconds:03}"

    def _generate_srt(
        self, segment_timestamps: list[SubtitleSegmentDict] | list[dict[str, Any]]
    ) -> str:
        """根据时间戳列表生成标准 SRT 格式字幕。

        Args:
            segment_timestamps (list[SubtitleSegmentDict] | list[dict[str, Any]]): 时间戳段落列表。

        Returns:
            str: SRT 格式字符串。
        """
        blocks = [
            f"{i + 1}\n{self.format_time(float(stamp['start']))} --> {self.format_time(float(stamp['end']))}\n{stamp.get('segment', stamp.get('text', ''))}\n\n"
            for i, stamp in enumerate(segment_timestamps)
        ]
        return "".join(blocks)

    def _generate_vtt(
        self, segment_timestamps: list[SubtitleSegmentDict] | list[dict[str, Any]]
    ) -> str:
        """根据时间戳列表生成 WebVTT 格式字幕。

        Args:
            segment_timestamps (list[SubtitleSegmentDict] | list[dict[str, Any]]): 时间戳段落列表。

        Returns:
            str: WebVTT 格式字符串。
        """
        blocks = ["WEBVTT\n\n"]
        for stamp in segment_timestamps:
            start_time_vtt = self.format_time(float(stamp["start"]), separator=".")
            end_time_vtt = self.format_time(float(stamp["end"]), separator=".")
            segment_text = str(stamp.get("segment", stamp.get("text", ""))).strip()
            blocks.append(f"{start_time_vtt} --> {end_time_vtt}\n{segment_text}\n\n")
        return "".join(blocks)

    def _generate_txt(
        self, segment_timestamps: list[SubtitleSegmentDict] | list[dict[str, Any]]
    ) -> str:
        """根据时间戳列表生成纯文本 TXT 字幕。

        Args:
            segment_timestamps (list[SubtitleSegmentDict] | list[dict[str, Any]]): 时间戳段落列表。

        Returns:
            str: 换行符连接的纯文本字符串。
        """
        return "\n".join(str(s.get("segment", s.get("text", ""))).strip() for s in segment_timestamps)

    def _generate_json(
        self, segment_timestamps: list[SubtitleSegmentDict] | list[dict[str, Any]]
    ) -> str:
        """根据时间戳列表生成 JSON 格式字幕数据。

        Args:
            segment_timestamps (list[SubtitleSegmentDict] | list[dict[str, Any]]): 时间戳段落列表。

        Returns:
            str: 格式化的 JSON 字符串。
        """
        return json.dumps(segment_timestamps, ensure_ascii=False, indent=4)

    def _generate_lrc(
        self, segment_timestamps: list[SubtitleSegmentDict] | list[dict[str, Any]]
    ) -> str:
        """根据时间戳列表生成歌词 LRC 格式字幕。

        Args:
            segment_timestamps (list[SubtitleSegmentDict] | list[dict[str, Any]]): 时间戳段落列表。

        Returns:
            str: LRC 格式字符串。
        """
        lines: list[str] = []
        for stamp in segment_timestamps:
            start_f = float(stamp["start"])
            minutes = int(start_f // SECONDS_PER_MINUTE)
            seconds = int(start_f % SECONDS_PER_MINUTE)
            milliseconds = int((start_f * CENTISECONDS_PER_SECOND) % CENTISECONDS_PER_SECOND)
            segment_text = str(stamp.get("segment", stamp.get("text", ""))).strip()
            lines.append(f"[{minutes:02}:{seconds:02}.{milliseconds:02}]{segment_text}\n")
        return "".join(lines)

    def _generate_word_srt(
        self, segment_timestamps: list[SubtitleSegmentDict] | list[dict[str, Any]]
    ) -> str:
        """生成逐词级 SRT：每个词作为独立字幕块。

        Args:
            segment_timestamps (list[SubtitleSegmentDict] | list[dict[str, Any]]): 包含 words 列表的段落。

        Returns:
            str: 逐词 SRT 格式字符串。
        """
        blocks: list[str] = []
        word_counter = 1

        for seg in segment_timestamps:
            words_in_seg = seg.get("words", [])

            # 如果没有 word 数据，回退到段落模式
            if not words_in_seg:
                blocks.append(
                    self._render_srt_block(
                        word_counter,
                        float(seg["start"]),
                        float(seg["end"]),
                        str(seg.get("segment", seg.get("text", ""))),
                    )
                )
                word_counter += 1
                continue

            for w in words_in_seg:
                word_text = str(w.get("word", "")).strip()
                if not word_text:
                    continue

                blocks.append(
                    self._render_srt_block(
                        word_counter,
                        float(w["start"]),
                        float(w["end"]),
                        word_text,
                    )
                )
                word_counter += 1

        return "".join(blocks)

    def _generate_char_srt(
        self, segment_timestamps: list[SubtitleSegmentDict] | list[dict[str, Any]]
    ) -> str:
        """生成逐字级 SRT：每个字符作为独立字幕块。

        Args:
            segment_timestamps (list[SubtitleSegmentDict] | list[dict[str, Any]]): 包含 chars 列表的段落。

        Returns:
            str: 逐字 SRT 格式字符串。
        """
        blocks: list[str] = []
        char_counter = 1

        for seg in segment_timestamps:
            chars_in_seg = seg.get("chars", [])

            # 如果没有 char 数据，回退到段落模式
            if not chars_in_seg:
                blocks.append(
                    self._render_srt_block(
                        char_counter,
                        float(seg["start"]),
                        float(seg["end"]),
                        str(seg.get("segment", seg.get("text", ""))),
                    )
                )
                char_counter += 1
                continue

            for c in chars_in_seg:
                char_text = str(c.get("char", ""))
                if not char_text:
                    continue

                blocks.append(
                    self._render_srt_block(
                        char_counter,
                        float(c["start"]),
                        float(c["end"]),
                        char_text,
                    )
                )
                char_counter += 1

        return "".join(blocks)

    def _generate_ass(
        self, segment_timestamps: list[SubtitleSegmentDict] | list[dict[str, Any]]
    ) -> str:
        """生成 ASS 格式字幕内容。

        Args:
            segment_timestamps (list[SubtitleSegmentDict] | list[dict[str, Any]]): 时间戳段落列表。

        Returns:
            str: 包含头部和对话事件的 ASS 字幕字符串。
        """
        header = (
            "[Script Info]\n"
            "; Script generated by SubtitleService\n"
            "Title: Generated Subtitles\n"
            "ScriptType: v4.00+\n"
            "WrapStyle: 0\n"
            "ScaledBorderAndShadow: yes\n"
            "YCbCr Matrix: TV.601\n"
            "PlayResX: 1920\n"
            "PlayResY: 1080\n"
            "\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,30,30,30,1\n"
            "\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

        lines: list[str] = []
        for stamp in segment_timestamps:
            start_t = self._format_ass_time(float(stamp["start"]))
            end_t = self._format_ass_time(float(stamp["end"]))
            text = str(stamp.get("segment", stamp.get("text", ""))).strip().replace("\n", "\\N")
            line = f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{text}"
            lines.append(line)

        return header + "\n".join(lines)

    def _format_ass_time(self, seconds: float) -> str:
        """格式化 ASS 时间: H:MM:SS.cc (centiseconds)。

        Args:
            seconds (float): 秒数。

        Returns:
            str: ASS 格式时间字符串。
        """
        if seconds < 0:
            seconds = 0.0
        hours = int(seconds // SECONDS_PER_HOUR)
        minutes = int((seconds % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE)
        secs = int(seconds % SECONDS_PER_MINUTE)
        centiseconds = int(round((seconds % 1) * CENTISECONDS_PER_SECOND))
        if centiseconds == CENTISECONDS_PER_SECOND:
            return self._format_ass_time(seconds + 0.01)

        return f"{hours}:{minutes:02}:{secs:02}.{centiseconds:02}"

    def _render_srt_block(
        self, index: int, start: float, end: float, text: str
    ) -> str:
        """渲染单个 SRT 字幕块。

        Args:
            index (int): 字幕编号。
            start (float): 开始时间秒数。
            end (float): 结束时间秒数。
            text (str): 字幕文本。

        Returns:
            str: 格式化的 SRT 字幕块。
        """
        return f"{index}\n{self.format_time(start)} --> {self.format_time(end)}\n{text}\n\n"

    def parse_srt(self, content: str) -> list[SubtitleSegmentDict]:
        """将 SRT 字符串解析为 segments 列表，支持 Windows CRLF 与 Unix LF 换行。

        Args:
            content (str): 待解析的 SRT 文本内容。

        Returns:
            list[SubtitleSegmentDict]: 解析出的字幕段落列表，每项包含 index, start, end, segment。
        """
        segments: list[SubtitleSegmentDict] = []
        if not content or not content.strip():
            return segments

        # 统一标准化换行符，同时在正则中兼容 \r?\n
        normalized_content = content.replace("\r\n", "\n").replace("\r", "\n")
        pattern = re.compile(
            r"(\d+)\r?\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\r?\n(.*?)(?=\r?\n\r?\n|\Z)",
            re.DOTALL,
        )

        for match in pattern.finditer(normalized_content):
            index, start_str, end_str, text = match.groups()
            segments.append(
                {
                    "index": int(index),
                    "start": self.srt_time_to_seconds(start_str),
                    "end": self.srt_time_to_seconds(end_str),
                    "segment": text.strip(),
                }
            )
        return segments

    def srt_time_to_seconds(self, time_str: str) -> float:
        """将 SRT 时间格式 (00:00:00,000) 转换为秒数。

        Args:
            time_str (str): 时间字符串。

        Returns:
            float: 转换后的秒数。
        """
        hours, mins, secs_ms = time_str.split(":")
        secs, ms = secs_ms.split(",")
        return (
            int(hours) * SECONDS_PER_HOUR
            + int(mins) * SECONDS_PER_MINUTE
            + int(secs)
            + int(ms) / float(MS_PER_SECOND)
        )

    # --- 向后兼容别名 ---
    def _format_time(self, seconds: float, separator: str = ",") -> str:
        """向后兼容别名方法。"""
        return self.format_time(seconds, separator)

    def _srt_time_to_seconds(self, time_str: str) -> float:
        """向后兼容别名方法。"""
        return self.srt_time_to_seconds(time_str)
