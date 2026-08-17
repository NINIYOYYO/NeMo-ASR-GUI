import asyncio
import os
from pathlib import Path
from typing import Any

from interfaces import (
    IConfigManager,
    ISubtitleGenerator,
    ITranslationController,
    ITranslationService,
)
from utils.logger import logger


def _read_file_text_sync(file_path: str) -> str:
    """同步读取文本文件内容（供 asyncio.to_thread 线程池调用）。

    Args:
        file_path (str): 文件路径。

    Returns:
        str: 文件文本内容。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def _write_file_text_sync(file_path: str, content: str) -> None:
    """同步写入文本文件内容（供 asyncio.to_thread 线程池调用）。

    Args:
        file_path (str): 文件路径。
        content (str): 待写入的文本内容。
    """
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)


class TranslationController(ITranslationController):
    """处理字幕翻译与 AI 智能断句相关 UI 事件的控制器。"""

    def __init__(
        self,
        subtitle_service: ISubtitleGenerator,
        translation_service: ITranslationService,
        config_manager: IConfigManager,
    ) -> None:
        """初始化翻译控制器。

        Args:
            subtitle_service (ISubtitleGenerator): 字幕生成与解析服务实例。
            translation_service (ITranslationService): 大模型翻译与断句服务实例。
            config_manager (IConfigManager): 配置管理器实例。
        """
        self.subtitle_service = subtitle_service
        self.translation_service = translation_service
        self.config = config_manager
        self.output_dir = (
            Path(__file__).resolve().parent.parent / "subtitles" / "translated"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _save_llm_config(
        self, api_key: str, base_url: str, model_name: str, proxy: str | None
    ) -> None:
        """保存 API 相关配置。

        Args:
            api_key (str): API 密钥。
            base_url (str): API 基础 URL。
            model_name (str): 模型名称。
            proxy (str | None): 可选代理地址。
        """
        self.config.save_config(
            api_key=api_key, base_url=base_url, llm_model=model_name, proxy=proxy
        )

    async def handle_translation(
        self,
        file_objs: list[Any],
        target_lang: str,
        is_bilingual: bool,
        api_key: str,
        base_url: str,
        model_name: str,
        proxy: str | None = None,
        concurrency: int = 5,
        chunk_size: int = 30,
    ) -> tuple[str, list[str] | None, str]:
        """处理翻译 UI 事件，异步调用大模型翻译并输出新字幕文件。

        Args:
            file_objs (list[Any]): 上传的字幕文件对象列表。
            target_lang (str): 目标语言名称。
            is_bilingual (bool): 是否生成双语字幕。
            api_key (str): API 密钥。
            base_url (str): API 基础 URL。
            model_name (str): 模型名称。
            proxy (str | None): 可选代理地址。
            concurrency (int): 并发数。
            chunk_size (int): 批次大小。

        Returns:
            tuple[str, list[str] | None, str]: (状态提示消息, 翻译后文件路径列表, 预览内容)。
        """
        if not api_key or not file_objs:
            return "错误：请上传文件并输入 API Key", None, ""

        self._save_llm_config(api_key, base_url, model_name, proxy)

        translated_files: list[str] = []
        last_preview = ""

        for file_obj in file_objs:
            try:
                file_path = (
                    file_obj.name if hasattr(file_obj, "name") else str(file_obj)
                )

                # 1. 异步非阻塞读取原始字幕
                content = await asyncio.to_thread(_read_file_text_sync, file_path)
                segments = self.subtitle_service.parse_srt(content)

                # 2. 调用翻译服务
                translated_segments = await self.translation_service.translate_segments(
                    segments,
                    target_lang,
                    api_key,
                    base_url,
                    model_name,
                    is_bilingual,
                    proxy=proxy,
                    concurrency=concurrency,
                    chunk_size=chunk_size,
                )

                # 3. 生成新字幕文件
                translated_content = self.subtitle_service.generate_content(
                    translated_segments, "srt"
                )

                original_name = os.path.basename(file_path)
                save_path = self.output_dir / f"{target_lang}_{original_name}"

                # 4. 异步非阻塞写入新字幕文件
                await asyncio.to_thread(
                    _write_file_text_sync, str(save_path), translated_content
                )

                translated_files.append(str(save_path))
                last_preview = translated_content

            except Exception as e:
                logger.error(f"处理翻译文件失败: {e}")
                continue

        return (
            f"成功翻译 {len(translated_files)} 个文件",
            translated_files if translated_files else None,
            last_preview,
        )

    async def handle_ai_segmentation(
        self,
        file_objs: list[Any],
        api_key: str,
        base_url: str,
        model_name: str,
        proxy: str | None = None,
        concurrency: int = 3,
        chunk_size: int = 50,
    ) -> tuple[str, list[str] | None]:
        """处理 AI 断句 UI 事件，异步调用大模型进行智能断句并重排时间轴。

        Args:
            file_objs (list[Any]): 上传的字幕文件对象列表。
            api_key (str): API 密钥。
            base_url (str): API 基础 URL。
            model_name (str): 模型名称。
            proxy (str | None): 可选代理地址。
            concurrency (int): 并发数。
            chunk_size (int): 批次大小。

        Returns:
            tuple[str, list[str] | None]: (状态提示消息, 断句后文件路径列表)。
        """
        if not api_key or not file_objs:
            return "错误：请上传文件并输入 API Key", None

        self._save_llm_config(api_key, base_url, model_name, proxy)
        segmented_files: list[str] = []

        for file_obj in file_objs:
            try:
                file_path = (
                    file_obj.name if hasattr(file_obj, "name") else str(file_obj)
                )

                # 1. 异步非阻塞读取原始字幕
                content = await asyncio.to_thread(_read_file_text_sync, file_path)
                segments = self.subtitle_service.parse_srt(content)

                # 2. 调用智能断句与 DP 锚点重对齐
                new_segments = await self.translation_service.segment_subtitles(
                    segments,
                    api_key,
                    base_url,
                    model_name,
                    proxy,
                    concurrency,
                    chunk_size,
                )

                content = self.subtitle_service.generate_content(new_segments, "srt")

                original_name = os.path.basename(file_path)
                save_path = self.output_dir / f"segmented_{original_name}"

                # 3. 异步非阻塞写入新字幕文件
                await asyncio.to_thread(_write_file_text_sync, str(save_path), content)
                segmented_files.append(str(save_path))
            except Exception as e:
                logger.error(f"AI 断句处理失败: {e}")

        return (
            f"成功处理 {len(segmented_files)} 个文件",
            segmented_files if segmented_files else None,
        )

