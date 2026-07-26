import os
from pathlib import Path

from interfaces import (
    IConfigManager,
    ISubtitleGenerator,
    ITranslationController,
    ITranslationService,
)
from utils.logger import logger


class TranslationController(ITranslationController):
    def __init__(
        self,
        subtitle_service: ISubtitleGenerator,
        translation_service: ITranslationService,
        config_manager: IConfigManager,
    ):
        self.subtitle_service = subtitle_service
        self.translation_service = translation_service
        self.config = config_manager
        self.output_dir = (
            Path(__file__).resolve().parent.parent / "subtitles" / "translated"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _save_llm_config(self, api_key, base_url, model_name, proxy):
        """保存 API 相关配置"""
        self.config.save_config(
            api_key=api_key, base_url=base_url, llm_model=model_name, proxy=proxy
        )

    async def handle_translation(
        self,
        file_objs: list,
        target_lang: str,
        is_bilingual: bool,
        api_key: str,
        base_url: str,
        model_name: str,
        proxy: str | None = None,
        concurrency: int = 5,
        chunk_size: int = 30,
    ):
        if not api_key or not file_objs:
            return "错误：请上传文件并输入 API Key", None, ""

        self._save_llm_config(api_key, base_url, model_name, proxy)

        translated_files = []
        last_preview = ""

        for file_obj in file_objs:
            try:
                # 1. 解析原始字幕
                with open(file_obj.name, "r", encoding="utf-8") as f:
                    content = f.read()
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

                original_name = os.path.basename(file_obj.name)
                save_path = self.output_dir / f"{target_lang}_{original_name}"

                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(translated_content)

                translated_files.append(str(save_path))
                last_preview = translated_content

            except Exception as e:
                logger.error(f"处理翻译文件失败: {e}")
                continue

        return (
            f"成功翻译 {len(translated_files)} 个文件",
            translated_files,
            last_preview,
        )

    async def handle_ai_segmentation(
        self,
        file_objs: list,
        api_key: str,
        base_url: str,
        model_name: str,
        proxy: str | None = None,
        concurrency: int = 3,
        chunk_size: int = 50,
    ):
        if not api_key or not file_objs:
            return "错误：请上传文件并输入 API Key", None

        self._save_llm_config(api_key, base_url, model_name, proxy)
        segmented_files = []
        for file_obj in file_objs:
            try:
                with open(file_obj.name, "r", encoding="utf-8") as f:
                    content = f.read()
                segments = self.subtitle_service.parse_srt(content)

                new_segments = await self.translation_service.segment_subtitles(
                    segments, api_key, base_url, model_name, proxy, concurrency, chunk_size
                )

                content = self.subtitle_service.generate_content(new_segments, "srt")

                original_name = os.path.basename(file_obj.name)
                save_path = self.output_dir / f"segmented_{original_name}"

                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(content)
                segmented_files.append(str(save_path))
            except Exception as e:
                logger.error(f"AI 断句处理失败: {e}")

        return f"成功处理 {len(segmented_files)} 个文件", segmented_files
