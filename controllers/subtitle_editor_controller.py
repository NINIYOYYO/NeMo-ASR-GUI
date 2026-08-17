"""字幕编辑器控制器模块。

提供字幕解析、表格数据双向同步、批量替换校对本以及校对持久化功能。
"""

import json
import os
from pathlib import Path
from typing import Any

from core.constants import DEFAULT_CORRECTIONS_FILENAME
from interfaces import ISubtitleEditorController, ISubtitleGenerator, SubtitleSegmentDict
from utils.logger import logger


class SubtitleEditorController(ISubtitleEditorController):
    """字幕编辑器与批量校对控制器。"""

    def __init__(self, subtitle_service: ISubtitleGenerator) -> None:
        """初始化字幕编辑器控制器。

        Args:
            subtitle_service (ISubtitleGenerator): 字幕生成与解析服务实例。
        """
        self.subtitle_service: ISubtitleGenerator = subtitle_service
        self.base_dir: Path = Path(__file__).resolve().parent.parent
        self.output_dir: Path = self.base_dir / "subtitles" / "edited"
        self.correction_file: Path = self.base_dir / DEFAULT_CORRECTIONS_FILENAME

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_list(self, data: Any) -> list[Any]:
        """将可能是 pandas DataFrame、FakeDataFrame 或 list 的数据安全转换为嵌套列表。

        Args:
            data (Any): 输入数据，可能为 DataFrame、FakeDataFrame、列表或 None。

        Returns:
            list[Any]: 标准二维列表。
        """
        if data is None:
            return []
        if isinstance(data, list):
            return data
        if hasattr(data, "values") and hasattr(data.values, "tolist"):
            return data.values.tolist()
        if hasattr(data, "to_numpy"):
            return data.to_numpy().tolist()
        if hasattr(data, "__iter__"):
            return [
                list(row)
                if hasattr(row, "__iter__") and not isinstance(row, (str, bytes))
                else row
                for row in data
            ]
        return []

    def load_subtitle_file(
        self, file_objs: list[Any]
    ) -> tuple[list[list[Any]] | None, str]:
        """加载字幕文件并解析为表格展示数据。

        Args:
            file_objs (list[Any]): 上传的文件对象列表。

        Returns:
            tuple[list[list[Any]] | None, str]: (表格数据列表, 状态提示文本)。
        """
        if not file_objs:
            return None, "未上传文件"

        first_file = file_objs[0]
        file_path = first_file.name if hasattr(first_file, "name") else str(first_file)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            segments = self.subtitle_service.parse_srt(content)
            df_data: list[list[Any]] = [
                [
                    s.get("index", idx + 1),
                    self.subtitle_service.format_time(float(s["start"])),
                    self.subtitle_service.format_time(float(s["end"])),
                    s.get("segment", s.get("text", "")),
                ]
                for idx, s in enumerate(segments)
            ]

            return df_data, f"成功加载: {os.path.basename(file_path)}"
        except Exception as e:
            logger.error(f"解析字幕失败: {e}")
            return None, f"解析失败: {e}"

    def apply_batch_corrections(
        self, subtitle_data: Any, correction_table: Any
    ) -> list[list[Any]]:
        """应用校对本中的批量替换逻辑。

        Args:
            subtitle_data (Any): 当前字幕表格数据。
            correction_table (Any): 校对规则替换表格。

        Returns:
            list[list[Any]]: 批量替换后的字幕数据列表。
        """
        sub_list = self._ensure_list(subtitle_data)
        corr_list = self._ensure_list(correction_table)

        if not corr_list or not sub_list:
            return sub_list

        # 提取有效的替换规则 (过滤空行)
        replacements: dict[str, str] = {}
        for row in corr_list:
            if len(row) >= 2 and row[0] and str(row[0]).strip():
                replacements[str(row[0]).strip()] = str(row[1]) if row[1] else ""

        if not replacements:
            return sub_list

        new_data: list[list[Any]] = []
        count = 0
        for row in sub_list:
            text = str(row[3]) if len(row) > 3 else ""
            for error, correct in replacements.items():
                if error in text:
                    text = text.replace(error, correct)
                    count += 1
            new_data.append([row[0], row[1], row[2], text])

        logger.info(f"批量校对完成，共替换 {count} 处。")
        return new_data

    def save_subtitles(self, subtitle_data: Any, original_file_obj: Any) -> str | None:
        """将表格数据保存回 SRT 字幕文件。

        Args:
            subtitle_data (Any): 编辑后的表格数据。
            original_file_obj (Any): 原始上传文件对象，用于提取基准文件名。

        Returns:
            str | None: 保存生成的文件路径，失败时返回 None。
        """
        subtitle_data_list = self._ensure_list(subtitle_data)

        if not subtitle_data_list:
            logger.warning("没有可保存的字幕数据")
            return None

        try:
            segments: list[SubtitleSegmentDict] = []
            for row in subtitle_data_list:
                # 兼容格式：SRT 常用逗号，有些库生成的可能带点
                start_str = str(row[1]).replace(".", ",")
                end_str = str(row[2]).replace(".", ",")
                segments.append(
                    {
                        "start": self.subtitle_service.srt_time_to_seconds(start_str),
                        "end": self.subtitle_service.srt_time_to_seconds(end_str),
                        "segment": str(row[3]),
                    }
                )

            content = self.subtitle_service.generate_content(segments, "srt")

            # 获取原始文件名
            if isinstance(original_file_obj, list) and original_file_obj:
                first_item = original_file_obj[0]
                original_name = os.path.basename(
                    first_item.name if hasattr(first_item, "name") else str(first_item)
                )
            elif original_file_obj is not None:
                original_name = os.path.basename(
                    original_file_obj.name
                    if hasattr(original_file_obj, "name")
                    else str(original_file_obj)
                )
            else:
                original_name = "subtitles.srt"

            save_path = self.output_dir / f"edited_{original_name}"
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content)

            return str(save_path)
        except Exception as e:
            logger.error(f"保存字幕文件失败: {e}")
            return None

    def load_corrections(self) -> list[list[str]]:
        """从本地加载校对本数据。

        Returns:
            list[list[str]]: 校对规则列表。
        """
        if self.correction_file.exists():
            try:
                with open(self.correction_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception as e:
                logger.error(f"加载校对本失败: {e}")
        return []

    def save_corrections(self, correction_table_data: Any) -> None:
        """保存校对本数据到本地 JSON 文件。

        Args:
            correction_table_data (Any): 校对规则表格数据。
        """
        data = self._ensure_list(correction_table_data)
        # 只保存非空行
        clean_data = [row for row in data if any(str(cell).strip() for cell in row)]
        try:
            with open(self.correction_file, "w", encoding="utf-8") as f:
                json.dump(clean_data, f, ensure_ascii=False, indent=4)
            logger.info("校对本已保存")
        except Exception as e:
            logger.error(f"保存校对本失败: {e}")