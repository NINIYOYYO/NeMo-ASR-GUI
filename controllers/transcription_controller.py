
import os
import re
import time
import zipfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

from interfaces import (
    CancellationToken,
    IASRService,
    IAudioService,
    ISubtitleGenerator,
    ITranscriptionController,
)
from utils.logger import logger


class TranscriptionController(ITranscriptionController):
    """处理转录相关 UI 事件与后台推理编排的控制器。"""

    def __init__(
        self,
        app_services: IASRService,
        audio_service: IAudioService,
        subtitle_generator: ISubtitleGenerator,
    ) -> None:
        """初始化转录控制器。

        Args:
            app_services (IASRService): ASR 语音识别服务实例。
            audio_service (IAudioService): 音频提取与处理服务实例。
            subtitle_generator (ISubtitleGenerator): 字幕生成服务实例。
        """
        self.app_services = app_services
        self.audio_service = audio_service
        self.subtitle_generator = subtitle_generator
        self.cancellation_token: CancellationToken = CancellationToken()

        self.subtitles_folder_path = (
            Path(__file__).resolve().parent.parent / "subtitles"
        )

        # 定义格式规格：{ 内部格式名: (文件名后缀, 最终文件扩展名) }
        self.FORMAT_SPECS: dict[str, tuple[str, str]] = {
            "word_srt": ("_word_srt", "srt"),
            "char_srt": ("_char_srt", "srt"),
        }

    def stop_transcription(self) -> str:
        """触发停止/取消当前正在执行的转录任务。

        Returns:
            str: 停止请求提示消息。
        """
        self.cancellation_token.cancel()
        logger.info("已发送转录任务取消信号。")
        return "已发送停止请求，正在中断后台推理..."

    def cancel(self) -> None:
        """协作式取消当前任务的快捷调用。"""
        self.cancellation_token.cancel()

    def process_media(
        self,
        media_file_objs: list[Any],
        chunk_length_s: int,
        output_formats: list[str],
        word_output_formats: list[str],
        enable_split: bool = False,
        max_chars: int = 0,
    ) -> Generator[tuple[str, list[str] | None, str], None, None]:
        """处理上传的视频/音频文件，分块推理并生成字幕文件。

        Args:
            media_file_objs (list[Any]): 上传的文件路径或对象列表。
            chunk_length_s (int): 音频分块长度（秒）。
            output_formats (list[str]): 输出字幕格式列表 (例如 ['srt', 'vtt'])。
            word_output_formats (list[str]): 额外的词/字级输出格式列表。
            enable_split (bool): 是否启用长字幕拆分。
            max_chars (int): 拆分时每条字幕的最大字符数。

        Yields:
            tuple[str, list[str] | None, str]: (状态提示文本, 生成的字幕文件路径列表, 预览文本)。
        """
        # 检查是否已处于取消状态
        if self.cancellation_token.is_cancelled:
            yield "转录任务已被用户取消。", None, ""
            return

        if not self.app_services.is_model_loaded:
            yield "错误：ASR 模型未加载。请先加载模型。", None, ""
            return

        if not media_file_objs:
            yield "请上传至少一个视频文件。", None, ""
            return

        requested_formats = list(set(output_formats + word_output_formats))
        logger.info(f"请求的输出格式: {requested_formats}")

        if not requested_formats:
            requested_formats = ["srt"]

        output_files_all: list[str] = []
        total_files = len(media_file_objs)
        start_time_total = time.time()
        generated_content_preview = ""

        for i, media_file_obj in enumerate(media_file_objs):
            if self.cancellation_token.is_cancelled:
                yield (
                    "转录任务已被用户取消。",
                    output_files_all if output_files_all else None,
                    generated_content_preview,
                )
                return

            input_media_path = (
                media_file_obj.name
                if hasattr(media_file_obj, "name")
                else str(media_file_obj)
            )
            file_name = os.path.basename(input_media_path)

            logger.info(
                f"开始处理视频/音频文件，当前: {i + 1}/{total_files}, 文件名: {file_name}"
            )
            yield (
                f"状态：正在处理文件, 当前：{i + 1}/{total_files}, 文件名：{file_name} ...",
                None,
                "",
            )

            extracted_audio_path = None
            output_path_for_download = None

            try:
                yield f"状态：正在提取 {file_name} 的音频...", None, ""
                extracted_audio_path = self.audio_service.extract_audio_from_video(
                    input_media_path
                )
                if not extracted_audio_path:
                    yield (
                        f"错误：{file_name} 音频提取失败。请检查视频文件或ffmpeg安装。正在跳过此文件。",
                        None,
                        "",
                    )
                    continue

                if self.cancellation_token.is_cancelled:
                    yield (
                        "转录任务已被用户取消。",
                        output_files_all if output_files_all else None,
                        generated_content_preview,
                    )
                    return

                chunk_length_ms = chunk_length_s * 1000
                yield (
                    f"状态：正在转录音频 (分块大小: {chunk_length_s}秒)...",
                    None,
                    "",
                )
                final_max_chars = max_chars if enable_split else 0

                try:
                    segment_timestamps = self.app_services.transcribe_audio_in_chunks(
                        extracted_audio_path,
                        chunk_length_ms,
                        final_max_chars,
                        cancellation_token=self.cancellation_token,
                    )
                except TypeError:
                    # 兼容未包含 cancellation_token 参数的自定义/Mock ASR 服务
                    segment_timestamps = self.app_services.transcribe_audio_in_chunks(
                        extracted_audio_path,
                        chunk_length_ms,
                        final_max_chars,
                    )

                if self.cancellation_token.is_cancelled:
                    yield (
                        "转录任务已被用户取消。",
                        output_files_all if output_files_all else None,
                        generated_content_preview,
                    )
                    return

                if not segment_timestamps:
                    yield (
                        f"警告：转录文件 {file_name} 未生成有效的时间戳。正在跳过此文件。",
                        None,
                        "",
                    )
                    continue

                original_base_name = os.path.basename(input_media_path).rsplit(".", 1)[
                    0
                ]
                base_name = self._sanitize_filename(original_base_name)

                yield f"状态：正在生成字幕文件 ({', '.join(requested_formats)})...", None, ""

                generated_content_preview = ""

                if not os.path.exists(self.subtitles_folder_path):
                    os.makedirs(self.subtitles_folder_path, exist_ok=True)

                for fmt in requested_formats:
                    try:
                        suffix, ext = self.FORMAT_SPECS.get(fmt, ("", fmt))
                        output_filename = f"{base_name}{suffix}.{ext}"

                        content = self.subtitle_generator.generate_content(
                            segment_timestamps, fmt
                        )
                        output_path_for_download = os.path.join(
                            self.subtitles_folder_path, output_filename
                        )
                        with open(
                            output_path_for_download, "w", encoding="utf-8"
                        ) as subtitle_file:
                            subtitle_file.write(content)
                        output_files_all.append(output_path_for_download)

                        if fmt == "srt" or generated_content_preview == "":
                            generated_content_preview = content
                    except Exception as e:
                        logger.error(f"生成 {fmt} 格式失败: {e}")
                    logger.info(f"字幕文件位于: {output_path_for_download}")

            except Exception as e:
                logger.error(f"处理文件 {file_name} 时发生未知错误: {e}", exc_info=True)
                yield (
                    f"错误：处理文件 {file_name} 时发生未知错误: {e}。正在跳过此文件。",
                    None,
                    "",
                )
                continue
            finally:
                if extracted_audio_path and os.path.exists(extracted_audio_path):
                    try:
                        os.remove(extracted_audio_path)
                    except OSError as e_clean:
                        logger.warning(
                            f"无法删除临时音频文件 {extracted_audio_path}: {e_clean}"
                        )

        elapsed_time_total = time.time() - start_time_total
        status_message = (
            f"处理完成。总耗时 {elapsed_time_total:.2f} 秒。生成 "
            f"{len(output_files_all)} 个字幕文件。"
        )
        logger.info(status_message)
        yield (
            status_message,
            output_files_all if output_files_all else None,
            generated_content_preview,
        )

    def create_zip_archive(self, file_objs: list[Any]) -> str | None:
        """将列表中的字幕文件打包成 ZIP 归档文件。

        Args:
            file_objs (list[Any]): 文件路径或带有 name 属性的文件对象列表。

        Returns:
            str | None: 生成的 ZIP 压缩包绝对路径，无文件或失败时返回 None。
        """
        if not file_objs:
            logger.warning("没有文件可打包")
            return None

        if not os.path.exists(self.subtitles_folder_path):
            os.makedirs(self.subtitles_folder_path, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        zip_filename = f"subtitles_package_{timestamp}.zip"
        zip_path = os.path.join(self.subtitles_folder_path, zip_filename)

        logger.info(f"开始打包 ZIP: {zip_path}")

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_obj in file_objs:
                    file_path = (
                        file_obj.name if hasattr(file_obj, "name") else str(file_obj)
                    )

                    if os.path.exists(file_path):
                        zipf.write(file_path, arcname=os.path.basename(file_path))
                    else:
                        logger.warning(f"打包时文件未找到: {file_path}")

            logger.info(f"ZIP 打包成功: {zip_path}")
            return zip_path

        except Exception as e:
            logger.error(f"打包 ZIP 失败: {e}", exc_info=True)
            return None

    def _sanitize_filename(self, filename: str) -> str:
        """替换 Windows / Linux 文件名中的非法字符。

        Args:
            filename (str): 原始文件名。

        Returns:
            str: 清洗后的安全文件名。
        """
        return re.sub(r'[\\/*?:"<>|]', "_", filename)

    