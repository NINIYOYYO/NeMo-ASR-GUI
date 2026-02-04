import os
import json
import pandas as pd
from pathlib import Path
from interfaces import ISubtitleEditorController, ISubtitleGenerator
from utils.logger import logger

class SubtitleEditorController(ISubtitleEditorController):
    def __init__(self, subtitle_service: ISubtitleGenerator):
        self.subtitle_service = subtitle_service
        self.base_dir = Path(__file__).resolve().parent.parent
        self.output_dir = self.base_dir / "subtitles" / "edited"
        self.correction_file = self.base_dir / "corrections.json"
        
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_list(self, data):
        """核心修复：将可能是 DataFrame 的数据安全转换为 list"""
        if isinstance(data, pd.DataFrame):
            return data.values.tolist()
        return data if data is not None else []

    def load_subtitle_file(self, file_objs: list):
        if not file_objs:
            return None, "未上传文件"
        
        file_path = file_objs[0].name
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            segments = self.subtitle_service.parse_srt(content)
            df_data = [[s["index"], 
                        self.subtitle_service._format_time(s["start"]), 
                        self.subtitle_service._format_time(s["end"]), 
                        s["segment"]] for s in segments]
            
            return df_data, f"成功加载: {os.path.basename(file_path)}"
        except Exception as e:
            logger.error(f"解析字幕失败: {e}")
            return None, f"解析失败: {e}"

    def apply_batch_corrections(self, subtitle_data, correction_table):
        # 转换数据类型
        subtitle_data = self._ensure_list(subtitle_data)
        correction_table = self._ensure_list(correction_table)

        if not correction_table or not subtitle_data:
            return subtitle_data

        # 提取有效的替换规则 (过滤空行)
        replacements = {}
        for row in correction_table:
            if len(row) >= 2 and row[0] and str(row[0]).strip():
                replacements[str(row[0]).strip()] = str(row[1]) if row[1] else ""
        
        if not replacements:
            return subtitle_data

        new_data = []
        count = 0
        for row in subtitle_data:
            text = str(row[3])
            for error, correct in replacements.items():
                if error in text:
                    text = text.replace(error, correct)
                    count += 1
            new_data.append([row[0], row[1], row[2], text])
        
        logger.info(f"批量校对完成，共替换 {count} 处。")
        return new_data

    def save_subtitles(self, subtitle_data, original_file_obj):
        # 修复 ValueError: 使用 .empty 或判断 None
        subtitle_data_list = self._ensure_list(subtitle_data)
        
        if not subtitle_data_list:
            logger.warning("没有可保存的字幕数据")
            return None
        
        try:
            segments = []
            for row in subtitle_data_list:
                # 兼容格式：SRT 常用逗号，有些库生成的可能带点
                start_str = str(row[1]).replace('.', ',')
                end_str = str(row[2]).replace('.', ',')
                segments.append({
                    "start": self.subtitle_service._srt_time_to_seconds(start_str),
                    "end": self.subtitle_service._srt_time_to_seconds(end_str),
                    "segment": str(row[3])
                })
            
            content = self.subtitle_service.generate_content(segments, "srt")
            
            # 获取原始文件名
            if isinstance(original_file_obj, list):
                original_name = os.path.basename(original_file_obj[0].name)
            else:
                original_name = os.path.basename(original_file_obj.name)

            save_path = self.output_dir / f"edited_{original_name}"
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content)
                
            return str(save_path)
        except Exception as e:
            logger.error(f"保存字幕文件失败: {e}")
            return None

    # --- 校对本持久化 ---
    def load_corrections(self) -> list:
        if self.correction_file.exists():
            try:
                with open(self.correction_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载校对本失败: {e}")
        return []

    def save_corrections(self, correction_table_data) -> None:
        data = self._ensure_list(correction_table_data)
        # 只保存非空行
        clean_data = [row for row in data if any(str(cell).strip() for cell in row)]
        try:
            with open(self.correction_file, "w", encoding="utf-8") as f:
                json.dump(clean_data, f, ensure_ascii=False, indent=4)
            logger.info("校对本已保存")
        except Exception as e:
            logger.error(f"保存校对本失败: {e}")