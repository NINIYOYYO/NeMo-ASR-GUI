"""转录后处理策略模块。

负责从 NeMo ASR 模型输出中提取三级嵌套数据（Segment、Char、Word）、自动断句拆分与日语字符级重组对齐。
"""

import textwrap
from abc import ABC, abstractmethod
from typing import Any

from core.constants import (
    DEFAULT_MAX_CHARS,
    DEFAULT_MAX_DURATION_SEC,
    DEFAULT_SOFT_LIMIT_CHARS,
    MIN_JAPANESE_SEGMENT_DURATION_SEC,
    MIN_SEGMENT_DURATION_SEC,
    SEGMENT_BOUNDARY_GUARD_SEC,
    SEGMENT_TOLERANCE_OFFSET_SEC,
    SILENCE_THRESHOLD_SEC,
    SPLIT_TOLERANCE_OFFSET_SEC,
)
from interfaces import CharTimestampDict, SubtitleSegmentDict, WordTimestampDict
from utils.logger import logger


class ITranscriptionStrategy(ABC):
    """转录后处理策略抽象接口。"""

    @abstractmethod
    def process(
        self,
        chunk_output_list: Any,
        chunk_offset_sec: float,
        max_chars: int = 0,
    ) -> list[SubtitleSegmentDict]:
        """处理模型输出的原始数据，返回标准化的字幕段落列表。

        Args:
            chunk_output_list (Any): NeMo 模型 transcribe 方法的返回结果。
            chunk_offset_sec (float): 当前音频块的起始时间偏移量（秒）。
            max_chars (int): 单句最大长度限制，0 表示不限制。

        Returns:
            list[SubtitleSegmentDict]: 包含 start, end, segment, chars, words 等字段的段落列表。
        """
        pass


class DefaultSegmentStrategy(ITranscriptionStrategy):
    """通用段落处理策略。

    功能：
    1. 提取 Segment, Char, Word 三级嵌套数据。
    2. 支持基于最大字符数的自动断句（Split）。
    3. 自动计算全局偏移时间。
    """

    def process(
        self,
        chunk_output_list: Any,
        chunk_offset_sec: float,
        max_chars: int = 0,
    ) -> list[SubtitleSegmentDict]:
        """处理主入口。

        Args:
            chunk_output_list (Any): 模型原始输出。
            chunk_offset_sec (float): 当前切片在全局轴上的偏移 (秒)。
            max_chars (int): 单句最大长度限制，0 表示不限制。

        Returns:
            list[SubtitleSegmentDict]: 标准化的段落列表。
        """
        # 1. 安全检查
        if (
            not chunk_output_list
            or not hasattr(chunk_output_list[0], "timestamp")
            or not chunk_output_list[0].timestamp
        ):
            logger.warning("模型未返回有效的时间戳数据。")
            return []

        raw_ts = chunk_output_list[0].timestamp

        # 2. 预提取并转换所有字符级和单词级数据（转换为全局时间）
        all_chars: list[CharTimestampDict] = self._extract_global_chars(raw_ts.get("char", []), chunk_offset_sec)
        all_words: list[WordTimestampDict] = self._extract_global_words(raw_ts.get("word", []), chunk_offset_sec)

        # 3. 提取原始段落并建立嵌套关系
        raw_segments: list[SubtitleSegmentDict] = []
        if "segment" in raw_ts:
            for seg_data in raw_ts["segment"]:
                g_start = float(seg_data["start"]) + chunk_offset_sec
                g_end = float(seg_data["end"]) + chunk_offset_sec
                text = str(seg_data.get("segment", seg_data.get("text", ""))).strip()

                if not text:
                    continue

                # 筛选属于该段落的子项 (使用 SEGMENT_TOLERANCE_OFFSET_SEC 容错偏移)
                sub_chars: list[CharTimestampDict] = [
                    c
                    for c in all_chars
                    if c["start"] >= g_start - SEGMENT_TOLERANCE_OFFSET_SEC
                    and c["end"] <= g_end + SEGMENT_TOLERANCE_OFFSET_SEC
                ]
                sub_words: list[WordTimestampDict] = [
                    w
                    for w in all_words
                    if w["start"] >= g_start - SEGMENT_TOLERANCE_OFFSET_SEC
                    and w["end"] <= g_end + SEGMENT_TOLERANCE_OFFSET_SEC
                ]

                raw_segments.append(
                    {
                        "start": g_start,
                        "end": g_end,
                        "segment": text,
                        "chars": sub_chars,
                        "words": sub_words,
                    }
                )

        # 4. 如果设置了最大长度限制，执行切分逻辑
        if max_chars > 0:
            return self._split_long_segments(raw_segments, max_chars)

        return raw_segments

    def _extract_global_chars(self, items: list[dict[str, Any]], offset: float) -> list[CharTimestampDict]:
        """将局部字符时间戳项转换为全局时间戳项。

        Args:
            items (list[dict[str, Any]]): 局部字符时间戳字典列表。
            offset (float): 全局时间偏移量（秒）。

        Returns:
            list[CharTimestampDict]: 全局字符时间戳字典列表。
        """
        results: list[CharTimestampDict] = []
        for item in items:
            results.append(
                {
                    "char": str(item.get("char", "")),
                    "start": float(item["start"]) + offset,
                    "end": float(item["end"]) + offset,
                }
            )
        return results

    def _extract_global_words(self, items: list[dict[str, Any]], offset: float) -> list[WordTimestampDict]:
        """将局部词级时间戳项转换为全局时间戳项。

        Args:
            items (list[dict[str, Any]]): 局部词级时间戳字典列表。
            offset (float): 全局时间偏移量（秒）。

        Returns:
            list[WordTimestampDict]: 全局词级时间戳字典列表。
        """
        results: list[WordTimestampDict] = []
        for item in items:
            results.append(
                {
                    "word": str(item.get("word", "")),
                    "start": float(item["start"]) + offset,
                    "end": float(item["end"]) + offset,
                }
            )
        return results

    def _split_long_segments(self, segments: list[SubtitleSegmentDict], max_chars: int) -> list[SubtitleSegmentDict]:
        """将超长句子切分为多行，并重新分配时间戳和嵌套项。

        Args:
            segments (list[SubtitleSegmentDict]): 原始段落列表。
            max_chars (int): 单行最大字符数。

        Returns:
            list[SubtitleSegmentDict]: 切分后的段落列表。
        """
        final_segments: list[SubtitleSegmentDict] = []

        for seg in segments:
            text = str(seg.get("segment", ""))

            # 如果没超过限制，直接添加
            if len(text) <= max_chars:
                final_segments.append(seg)
                continue

            # 计算需要切成几段：优先按空格切分（针对英文），如果是中日文则按字符强制切分
            if " " in text:
                sub_texts = textwrap.wrap(text, width=max_chars, break_long_words=True)
            else:
                sub_texts = [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

            # 为每一段分配时间
            total_duration = float(seg["end"]) - float(seg["start"])
            total_chars = max(1, len(text))
            current_start = float(seg["start"])

            chars_pool = seg.get("chars", [])
            words_pool = seg.get("words", [])

            for sub_text in sub_texts:
                sub_len = len(sub_text)
                # 比例计算法分配时长 (Duration = 总时长 * 子句字符占比)
                sub_duration = total_duration * (sub_len / total_chars)
                current_end = current_start + sub_duration

                # 从原始段落的嵌套库里筛选属于子句时间范围的项
                sub_chars: list[CharTimestampDict] = [
                    c
                    for c in chars_pool
                    if c["start"] >= current_start - SPLIT_TOLERANCE_OFFSET_SEC
                    and c["end"] <= current_end + SPLIT_TOLERANCE_OFFSET_SEC
                ]
                sub_words: list[WordTimestampDict] = [
                    w
                    for w in words_pool
                    if w["start"] >= current_start - SPLIT_TOLERANCE_OFFSET_SEC
                    and w["end"] <= current_end + SPLIT_TOLERANCE_OFFSET_SEC
                ]

                final_segments.append(
                    {
                        "start": current_start,
                        "end": current_end,
                        "segment": sub_text.strip(),
                        "chars": sub_chars,
                        "words": sub_words,
                    }
                )

                current_start = current_end

        return final_segments


class JapaneseCharStrategy(ITranscriptionStrategy):
    """日语字符级重组策略。

    适用于 Parakeet 日语 TDT 模型，支持嵌套输出和长度限制。
    """

    def process(
        self,
        chunk_output_list: Any,
        chunk_offset_sec: float,
        max_chars: int = 0,
    ) -> list[SubtitleSegmentDict]:
        """处理主入口。

        Args:
            chunk_output_list (Any): 模型输出列表。
            chunk_offset_sec (float): 当前切片全局时间偏移量（秒）。
            max_chars (int): 用户设置的最大字符数限制。

        Returns:
            list[SubtitleSegmentDict]: 格式化重组后的日语字幕段落。
        """
        # 1. 安全检查
        if (
            not chunk_output_list
            or not hasattr(chunk_output_list[0], "timestamp")
            or not chunk_output_list[0].timestamp
        ):
            return []

        # 2. 提取所有 Char 并转换为全局时间
        char_timestamps: list[CharTimestampDict] = []
        if "char" in chunk_output_list[0].timestamp:
            current_chunk_chars = chunk_output_list[0].timestamp["char"]
            for char_data in current_chunk_chars:
                char_c = char_data.get("char")
                if isinstance(char_c, list):
                    char_c = "".join(char_c)

                char_timestamps.append(
                    {
                        "char": str(char_c) if char_c is not None else "",
                        "start": float(char_data["start"]) + chunk_offset_sec,
                        "end": float(char_data["end"]) + chunk_offset_sec,
                    }
                )

        # 3. 调用重组算法 (将 UI 的 max_chars 传入作为硬限制)
        return self._group_chars_into_segments(char_timestamps, user_max_chars=max_chars)

    def _group_chars_into_segments(
        self,
        char_timestamps: list[CharTimestampDict],
        max_duration: float = DEFAULT_MAX_DURATION_SEC,
        user_max_chars: int = 0,
    ) -> list[SubtitleSegmentDict]:
        """智能日语字符重组与分句算法。

        Args:
            char_timestamps (list[CharTimestampDict]): 字符时间戳列表。
            max_duration (float): 单句最大持续时间（秒）。
            user_max_chars (int): 用户指定的最大字符限制。

        Returns:
            list[SubtitleSegmentDict]: 重构后的字幕段落列表。
        """
        if not char_timestamps:
            return []

        segments: list[SubtitleSegmentDict] = []
        current_segment_objs: list[CharTimestampDict] = []
        current_segment_start: float | None = None

        # 断句逻辑配置
        strong_endings = {"。", "！", "？", "!", "?", "…", ".", "\n"}
        weak_pauses = {"、", "，", ",", " ", "　"}

        # 如果 UI 设置了长度，优先使用 UI 的设置，否则使用默认常量
        hard_limit = user_max_chars if user_max_chars > 0 else DEFAULT_MAX_CHARS
        soft_limit = min(DEFAULT_SOFT_LIMIT_CHARS, hard_limit)

        for i, char_data in enumerate(char_timestamps):
            char_text = char_data["char"]
            char_start = char_data["start"]
            char_end = char_data["end"]

            if not char_text:
                continue

            if current_segment_start is None:
                current_segment_start = char_start

            current_segment_objs.append(char_data)

            # 判断是否需要断句
            should_break = False
            is_last_char = i == len(char_timestamps) - 1

            # 计算静音间隙
            time_gap = 0.0
            if not is_last_char:
                next_char_start = char_timestamps[i + 1]["start"]
                time_gap = next_char_start - char_end

            current_text_len = len(current_segment_objs)
            current_duration = char_end - current_segment_start

            # 断句规则判断
            if char_text in strong_endings:
                should_break = True
            elif time_gap > SILENCE_THRESHOLD_SEC:
                should_break = True
            elif current_text_len >= hard_limit:
                should_break = True
            elif current_text_len >= soft_limit and char_text in weak_pauses:
                should_break = True
            elif current_duration >= max_duration:
                if not is_last_char and char_timestamps[i + 1]["char"] not in strong_endings:
                    should_break = True

            # 执行断句
            if should_break or is_last_char:
                segment_text = "".join([c["char"] for c in current_segment_objs]).strip()

                # 过滤纯标点的无效段落
                if segment_text and not all(c in weak_pauses or c in strong_endings for c in segment_text):
                    final_end = char_end

                    # 确保最短时长
                    if (final_end - current_segment_start) < MIN_JAPANESE_SEGMENT_DURATION_SEC:
                        final_end = max(final_end, current_segment_start + MIN_JAPANESE_SEGMENT_DURATION_SEC)

                    # 防止时间轴重叠并杜绝负时隙倒流
                    if not is_last_char:
                        next_start = char_timestamps[i + 1]["start"]
                        if final_end >= next_start:
                            final_end = max(
                                current_segment_start + MIN_SEGMENT_DURATION_SEC,
                                next_start - SEGMENT_BOUNDARY_GUARD_SEC,
                            )

                    # 保底确保结束时间不早于起始时间
                    if final_end < current_segment_start:
                        final_end = current_segment_start + MIN_SEGMENT_DURATION_SEC

                    segments.append(
                        {
                            "start": current_segment_start,
                            "end": final_end,
                            "segment": segment_text,
                            "chars": list(current_segment_objs),
                            "words": [],
                        }
                    )

                # 重置当前段落
                current_segment_objs = []
                current_segment_start = None

        return segments
