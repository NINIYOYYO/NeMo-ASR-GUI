import textwrap
from abc import ABC, abstractmethod

from utils.logger import logger


class ITranscriptionStrategy(ABC):
    """
    转录后处理策略接口。
    规定了所有处理器都必须实现 process 方法。
    """
    @abstractmethod
    def process(self, chunk_output_list, chunk_offset_sec: float,  max_chars: int = 0) -> list:
        """
        处理模型输出的原始数据，返回标准化的字幕段落列表。
        Args:
            chunk_output_list: NeMo 模型 transcribe 方法的返回结果
            chunk_offset_sec: 当前音频块的起始时间偏移量（秒）
            max_chars: 单句最大长度限制，0 表示不限制
        Returns:
            list: [{'start': float, 'end': float, 'segment': str}, ...]
        """
        pass

class DefaultSegmentStrategy(ITranscriptionStrategy):
    """
    【策略 A】: 增强型默认段落处理策略。
    功能：
    1. 提取 Segment, Char, Word 三级嵌套数据。
    2. 支持基于最大字符数的自动断句（Split）。
    3. 自动计算全局偏移时间。
    """

    def process(self, chunk_output_list, chunk_offset_sec: float, max_chars: int = 0) -> list:
        """
        处理主入口
        Args:
            chunk_output_list: 模型原始输出
            chunk_offset_sec: 当前切片在全球轴上的偏移(秒)
            max_chars: 单句最大长度限制，0 表示不限制
        """
        # 1. 安全检查
        if not chunk_output_list or not hasattr(chunk_output_list[0], "timestamp") or not chunk_output_list[0].timestamp:
            logger.warning("模型未返回有效的时间戳数据。")
            return []

        raw_ts = chunk_output_list[0].timestamp
        
        # 2. 预提取并转换所有字符级和单词级数据（转换为全局时间）
        all_chars = self._extract_global_items(raw_ts.get("char", []), chunk_offset_sec, "char")
        all_words = self._extract_global_items(raw_ts.get("word", []), chunk_offset_sec, "word")

        # 3. 提取原始段落并建立嵌套关系
        raw_segments = []
        if "segment" in raw_ts:
            for seg_data in raw_ts["segment"]:
                g_start = seg_data["start"] + chunk_offset_sec
                g_end = seg_data["end"] + chunk_offset_sec
                text = seg_data.get("segment", seg_data.get("text", "")).strip()

                if not text:
                    continue

                # 筛选属于该段落的子项 (使用 0.05s 的容错偏移)
                sub_chars = [c for c in all_chars if c["start"] >= g_start - 0.05 and c["end"] <= g_end + 0.05]
                sub_words = [w for w in all_words if w["start"] >= g_start - 0.05 and w["end"] <= g_end + 0.05]

                raw_segments.append({
                    "start": g_start,
                    "end": g_end,
                    "segment": text,
                    "chars": sub_chars,
                    "words": sub_words
                })

        # 4. 如果设置了最大长度限制，执行切分逻辑
        if max_chars > 0:
            return self._split_long_segments(raw_segments, max_chars)
        
        return raw_segments

    def _extract_global_items(self, items: list, offset: float, key_name: str) -> list:
        """将局部时间戳项转换为全局时间戳项"""
        results = []
        for item in items:
            results.append({
                key_name: item.get(key_name, ""),
                "start": item["start"] + offset,
                "end": item["end"] + offset
            })
        return results

    def _split_long_segments(self, segments: list, max_chars: int) -> list:
        """
        将超长句子切分为多行，并重新分配时间戳和嵌套项
        """
        final_segments = []
        
        for seg in segments:
            text = seg["segment"]
            
            # 如果没超过限制，直接添加
            if len(text) <= max_chars:
                final_segments.append(seg)
                continue

            # 计算需要切成几段
            # 优先按空格切分（针对英文），如果是中日文则按字符强制切分
            if " " in text:
                sub_texts = textwrap.wrap(text, width=max_chars, break_long_words=True)
            else:
                sub_texts = [text[i:i+max_chars] for i in range(0, len(text), max_chars)]

            # 为每一段分配时间
            total_duration = seg["end"] - seg["start"]
            total_chars = len(text)
            current_start = seg["start"]

            for sub_text in sub_texts:
                sub_len = len(sub_text)
                # 比例计算法分配时长 (Duration = 总时长 * 子句字符占比)
                sub_duration = total_duration * (sub_len / total_chars)
                current_end = current_start + sub_duration

                # 从原始段落的嵌套库里筛选属于子句时间范围的项
                sub_chars = [c for c in seg["chars"] if c["start"] >= current_start - 0.02 and c["end"] <= current_end + 0.02]
                sub_words = [w for w in seg["words"] if w["start"] >= current_start - 0.02 and w["end"] <= current_end + 0.02]

                final_segments.append({
                    "start": current_start,
                    "end": current_end,
                    "segment": sub_text.strip(),
                    "chars": sub_chars,
                    "words": sub_words
                })
                
                current_start = current_end # 下一段的开始是这一段的结束

        return final_segments

class JapaneseCharStrategy(ITranscriptionStrategy):
    """
    【策略 B】: 日语字符级重组策略 (V3 增强版)。
    适用于 Parakeet 日语 TDT 模型，支持嵌套输出和长度限制。
    """

    def process(self, chunk_output_list, chunk_offset_sec: float, max_chars: int = 0) -> list:
        """
        处理主入口
        """
        # 1. 安全检查
        if not chunk_output_list or not hasattr(chunk_output_list[0], "timestamp") or not chunk_output_list[0].timestamp:
            return []

        # 2. 提取所有 Char 并转换为全局时间
        char_timestamps = []
        if "char" in chunk_output_list[0].timestamp:
            current_chunk_chars = chunk_output_list[0].timestamp["char"]
            for char_data in current_chunk_chars:
                char_c = char_data.get('char')
                if isinstance(char_c, list): # 处理某些异常输出
                    char_c = "".join(char_c)
                
                char_timestamps.append({
                    "char": char_c,
                    "start": char_data["start"] + chunk_offset_sec,
                    "end": char_data["end"] + chunk_offset_sec
                })
        
        # 3. 调用重组算法 (将 UI 的 max_chars 传入作为硬限制)
        return self._group_chars_into_segments(char_timestamps, user_max_chars=max_chars)

    def _group_chars_into_segments(
        self, char_timestamps: list, max_duration: float = 8.0, user_max_chars: int = 0
    ) -> list:
        """
        V3 智能断句算法 - 嵌套增强版
        """
        if not char_timestamps:
            return []

        segments = []
        current_segment_objs = [] # 存储带时间戳的字符对象
        current_segment_start = None

        # 断句逻辑配置
        strong_endings = {'。', '！', '？', '!', '?', '…', '.', '\n'}
        weak_pauses = {'、', '，', ',', ' ', '　'}
        SILENCE_THRESHOLD = 0.45
        
        # 如果 UI 设置了长度，优先使用 UI 的设置，否则默认 40
        hard_limit = user_max_chars if user_max_chars > 0 else 40
        soft_limit = min(20, hard_limit) # 软限制通常是硬限制的一半

        for i, char_data in enumerate(char_timestamps):
            char_text = char_data['char']
            char_start = char_data['start']
            char_end = char_data['end']

            if not char_text:
                continue

            if current_segment_start is None:
                current_segment_start = char_start

            current_segment_objs.append(char_data)

            # 判断是否需要断句
            should_break = False
            is_last_char = (i == len(char_timestamps) - 1)

            # 计算静音间隙
            time_gap = 0.0
            if not is_last_char:
                next_char_start = char_timestamps[i + 1]['start']
                time_gap = next_char_start - char_end

            current_text_len = len(current_segment_objs)
            current_duration = char_end - current_segment_start

            # 断句规则判断
            if char_text in strong_endings:
                should_break = True
            elif time_gap > SILENCE_THRESHOLD:
                should_break = True
            elif current_text_len >= hard_limit:
                should_break = True
            elif current_text_len >= soft_limit and char_text in weak_pauses:
                should_break = True
            elif current_duration >= max_duration:
                # 超过最大时长且下一个不是强结束符
                if not is_last_char and char_timestamps[i + 1]['char'] not in strong_endings:
                    should_break = True

            # 执行断句
            if should_break or is_last_char:
                # 组装文本
                segment_text = "".join([c['char'] for c in current_segment_objs]).strip()
                
                # 过滤纯标点的无效段落
                if segment_text and not all(c in weak_pauses or c in strong_endings for c in segment_text):
                    final_end = char_end
                    
                    # 确保最短时长
                    if (final_end - current_segment_start) < 0.5:
                        final_end = max(final_end, current_segment_start + 0.5)

                    # 防止时间轴重叠并杜绝负时隙倒流
                    if not is_last_char:
                        next_start = char_timestamps[i + 1]["start"]
                        if final_end >= next_start:
                            final_end = max(current_segment_start + 0.05, next_start - 0.01)

                    # 保底确保结束时间不早于起始时间
                    if final_end < current_segment_start:
                        final_end = current_segment_start + 0.05

                    # --- 核心：返回符合嵌套标准的数据结构 ---
                    segments.append({
                        'start': current_segment_start,
                        'end': final_end,
                        'segment': segment_text,
                        'chars': list(current_segment_objs), # 浅拷贝字符对象列表
                        'words': [] # 日语模型通常不提供 word 级数据，返回空列表以兼容
                    })

                # 重置当前段落
                current_segment_objs = []
                current_segment_start = None

        return segments