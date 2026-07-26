
from interfaces import ISubtitleGenerator
import re


class SubtitleService(ISubtitleGenerator):
    """
    生成多种格式字幕文件内容的服务。
    支持: SRT, VTT, TXT, JSON, LRC, ASS
    """
       

    def generate_content(self, segment_timestamps: list, format_type: str) -> str:
        """根据时间戳列表生成 SRT 格式的字幕内容。
        ARGS:
            segment_timestamps: 包含 {'start': float, 'end': float, 'segment': str} 的列表。
            format_type: 格式类型 (e.g., 'srt', 'vtt', 'txt', 'json')
        RETURNS:
            SRT 格式的字符串。
        """
        method_name = f"_generate_{format_type.lower()}"
        if hasattr(self, method_name):
            return getattr(self, method_name)(segment_timestamps)
        else:
            raise ValueError(f"不支持的字幕格式: {format_type}")

    def _format_time(self, seconds, separator=",") -> str:
        """
        格式化时间: HH:MM:SS,mmm (SRT) 或 HH:MM:SS.mmm (VTT)
        先整体四舍五入到毫秒再拆分，避免浮点截断误差（如 1.001s 被截成 1,000）
        """
        if seconds < 0:
            seconds = 0
        total_ms = int(round(seconds * 1000))
        hours, rem = divmod(total_ms, 3600_000)
        minutes, rem = divmod(rem, 60_000)
        secs, milliseconds = divmod(rem, 1000)
        return f"{hours:02}:{minutes:02}:{secs:02}{separator}{milliseconds:03}"



    def _generate_srt(self, segment_timestamps: list) -> str:
        """
        根据时间戳列表生成 SRT 格式的字幕内容。
        ARGS:
            segment_timestamps: 包含 {'start': float, 'end': float, 'segment': str} 的列表。
        RETURNS:
            SRT 格式的字符串。
        """
        content = ""
        for i, stamp in enumerate(segment_timestamps):
            subtitle_number = i + 1
            start_time_srt = self._format_time(stamp["start"])
            end_time_srt = self._format_time(stamp["end"])
            segment_text = stamp["segment"]
            srt_block = f"{subtitle_number}\n{start_time_srt} --> {end_time_srt}\n{segment_text}\n\n"
            content += srt_block
        return content

    def _generate_vtt(self, segment_timestamps: list) -> str:
        """
        根据时间戳列表生成 VTT 格式的字幕内容。
        ARGS:
            segment_timestamps: 包含 {'start': float, 'end': float, 'segment': str} 的列表。
        RETURNS:
            VTT 格式的字符串。
        """
        content = "WEBVTT\n\n"
        for stamp in segment_timestamps:
            start_time_vtt = self._format_time(stamp["start"], separator=".")
            end_time_vtt = self._format_time(stamp["end"], separator=".")
            segment_text = stamp["segment"].strip()
            vtt_block = f"{start_time_vtt} --> {end_time_vtt}\n{segment_text}\n\n"
            content += vtt_block
        return content

    def _generate_txt(self, segement_timestamps: list) -> str:
        """
        根据时间戳列表生成 TXT 格式的字幕内容。
        ARGS:
            segment_timestamps: 包含 {'start': float, 'end': float, 'segment': str} 的列表。
        RETURNS:
            TXT 格式的字符串。
        """
        return "\n".join([s["segment"].strip() for s in segement_timestamps])
    
    def _generate_json(self, segment_timestamps: list) -> str:
        """
        根据时间戳列表生成 JSON 格式的字幕内容。
        ARGS:
            segment_timestamps: 包含 {'start': float, 'end': float, 'segment': str} 的列表。
        RETURNS:
            JSON 格式的字符串。
        """
        import json
        return json.dumps(segment_timestamps, ensure_ascii=False, indent=4)
    
    def _generate_lrc(self, segment_timestamps: list) -> str:
        """
        根据时间戳列表生成 LRC 格式的字幕内容。
        ARGS:
            segment_timestamps: 包含 {'start': float, 'end': float, 'segment': str} 的列表。
        RETURNS:
            LRC 格式的字符串。
        """
        content = ""
        for stamp in segment_timestamps:
            minutes = int(stamp["start"] // 60)
            seconds = int(stamp["start"] % 60)
            milliseconds = int((stamp["start"] * 100) % 100)
            segment_text = stamp["segment"].strip()
            lrc_line = f"[{minutes:02}:{seconds:02}.{milliseconds:02}]{segment_text}\n"
            content += lrc_line
        return content
    
    def _generate_word_srt(self, segment_timestamps: list) -> str:
        """
        生成单词级 SRT：每个单词作为一个独立的字幕块
        """
        content = ""
        word_counter = 1
        
        for seg in segment_timestamps:
            words_in_seg = seg.get("words", [])
            
            # 如果没有 word 数据，回退到段落模式
            if not words_in_seg:
                content += self._render_srt_block(word_counter, seg["start"], seg["end"], seg["segment"])
                word_counter += 1
                continue

            for w in words_in_seg:
                word_text = w["word"].strip()
                if not word_text: continue
                
                content += self._render_srt_block(
                    word_counter, 
                    w["start"], 
                    w["end"], 
                    word_text
                )
                word_counter += 1
                
        return content
    
    def _generate_char_srt(self, segment_timestamps: list) -> str:
        """
        生成char级 SRT：每个单词作为一个独立的字幕块
        """
        content = ""
        char_counter = 1
        
        for seg in segment_timestamps:
            chars_in_seg = seg.get("chars", [])
            
            # 如果没有 word 数据，回退到段落模式
            if not chars_in_seg:
                content += self._render_srt_block(char_counter, seg["start"], seg["end"], seg["segment"])
                char_counter += 1
                continue

            for c in chars_in_seg:
                char_text = c["char"]
                if not char_text: continue
                
                content += self._render_srt_block(
                    char_counter, 
                    c["start"], 
                    c["end"], 
                    char_text
                )
                char_counter += 1
                
        return content
    
    def _generate_ass(self, segment_timestamps: list) -> str:
        """
        生成 ASS 格式字幕内容。
        增加了 PlayResX/Y 定义以确保字体大小正常显示。
        """
        # 1. 定义 ASS 文件头 (添加了分辨率和更好的默认样式)
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
            # 这里的 Fontsize: 48 在 1080p 下比较合适。颜色格式为 &HAABBGGRR (Alpha, Blue, Green, Red)
            "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,30,30,30,1\n"
            "\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

        lines = []
        for stamp in segment_timestamps:
            start_t = self._format_ass_time(stamp["start"])
            end_t = self._format_ass_time(stamp["end"])
            
            # 清洗文本：去除首尾空格，替换换行，转义特定的符号
            text = stamp["segment"].strip().replace("\n", "\\N")
            
            # 组装对话行
            line = f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{text}"
            lines.append(line)

        return header + "\n".join(lines)

    def _format_ass_time(self, seconds: float) -> str:
        """
        格式化 ASS 时间: H:MM:SS.cc (centiseconds)
        """
        if seconds < 0: seconds = 0
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        # 修正：保证是两位数的百分之一秒
        centiseconds = int(round((seconds % 1) * 100))
        if centiseconds == 100: # 处理进位
            return self._format_ass_time(seconds + 0.01)
            
        return f"{hours}:{minutes:02}:{secs:02}.{centiseconds:02}"
    
    def _render_srt_block(self, index, start, end, text) -> str:
        return f"{index}\n{self._format_time(start)} --> {self._format_time(end)}\n{text}\n\n"
    



    def parse_srt(self, content: str) -> list:
        """将 SRT 字符串解析为 segments 列表"""
        segments = []
        # 正则匹配 SRT 块
        pattern = re.compile(r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\Z)', re.DOTALL)
        
        for match in pattern.finditer(content):
            index, start_str, end_str, text = match.groups()
            segments.append({
                "index": int(index),
                "start": self._srt_time_to_seconds(start_str),
                "end": self._srt_time_to_seconds(end_str),
                "segment": text.strip()
            })
        return segments

    def _srt_time_to_seconds(self, time_str: str) -> float:
        """SRT 时间格式 (00:00:00,000) 转秒"""
        hours, mins, secs_ms = time_str.split(':')
        secs, ms = secs_ms.split(',')
        return int(hours) * 3600 + int(mins) * 60 + int(secs) + int(ms) / 1000.0