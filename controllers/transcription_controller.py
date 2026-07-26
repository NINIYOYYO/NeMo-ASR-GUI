
import os
import re
import time
from pathlib import Path
import zipfile
from interfaces import IASRService
from interfaces import ITranscriptionController, IAudioService, ISubtitleGenerator
from utils.exceptions import TranscriptionError
from utils.logger import logger 


class TranscriptionController(ITranscriptionController):
    """
    一个专门处理转录相关 UI 事件的控制器。
    """

    def __init__(self, app_services: IASRService, audio_service: IAudioService, subtitle_generator: ISubtitleGenerator) -> None:
       
        self.app_services = app_services
        self.audio_service = audio_service
        self.subtitle_generator = subtitle_generator
        
        self.subtitles_folder_path = Path(__file__).resolve().parent.parent / "subtitles"

          # 定义格式规格：{ 内部格式名: (文件名后缀, 最终文件扩展名) }
        self.FORMAT_SPECS = {
            "word_srt": ("_word_srt", "srt"),
            "char_srt": ("_char_srt", "srt"),
            # 默认情况下，后缀为空，扩展名即为格式名本身
        }

    
    def process_media(self, media_file_objs: list, chunk_length_s: int, output_formats: list, word_output_formats: list, enable_split: bool = False, max_chars: int = 0):
        """处理上传的视频/音频文件，生成字幕文件。
        ARGS:
            media_file_objs: Gradio 上传的视频/音频文件对象列表。
            chunk_length_s: 音频分块长度（秒）。
            outpu_formats: 输出字幕格式列表 (e.g., ['srt', 'vtt'])
            word_output_formats: 额外的输出格式列表
            enable_split: 是否启用长字幕拆分。
            max_chars: 拆分时每个字幕的最大字符数。
        YIELDS:
            状态消息 (str), 输出 字幕 文件路径列表 (list), 字幕 内容预览。
        """

        if not self.app_services.is_model_loaded:
            yield "错误：ASR 模型未加载。请先加载模型。", None, ""
            return

        if media_file_objs is None:
            yield "请上传至少一个视频文件。", None, ""
            return
        output_formats = list(set(output_formats + word_output_formats))

        logger.info(f"请求的输出格式: {output_formats}")

        if not output_formats:
            output_formats = ['srt']

        output_files_all = []
        total_files = len(media_file_objs)
        start_time_total = time.time()
        generated_content_preview = ""  # 提前初始化，防止所有文件都失败时最终 yield 引用未定义变量

        for i, media_file_obj in enumerate(media_file_objs):
            input_media_path = media_file_obj  # Gradio Video 对象具有 .name 属性表示路径
            file_name = os.path.basename(input_media_path)

            logger.info(f"开始处理视频/音频文件， 当前: {i+1}/{total_files}, 文件名: {file_name}")
            yield f"状态：正在处理文件, 当前：{i+1}/{total_files}, 文件名：{file_name} ...", None, ""

            extracted_audio_path = None
            output_path_for_download = None  # 用于 Gradio File 组件

            try:
                yield f"状态：正在提取 {file_name} 的音频...", None, ""
                extracted_audio_path = self.audio_service.extract_audio_from_video(input_media_path)
                if not extracted_audio_path:
                    # 单个文件提取失败时跳过该文件，继续处理批量队列中的其余文件
                    yield f"错误：{file_name} 音频提取失败。请检查视频文件或ffmpeg安装。正在跳过此文件。", None, ""
                    continue

                chunk_length_ms = chunk_length_s * 1000
                yield f"状态：正在转录音频 (分块大小: {chunk_length_s}秒)...", None, ""
                final_max_chars = max_chars if enable_split else 0
         
                segment_timestamps = self.app_services.transcribe_audio_in_chunks(
                        extracted_audio_path, chunk_length_ms, final_max_chars
                        )
                    

                if not segment_timestamps:
                    yield f"警告：转录文件 {file_name} 未生成有效的时间戳。正在跳过此文件。", None, ""
                    continue

                original_base_name = os.path.basename(input_media_path).rsplit(".", 1)[0]
                base_name = self._sanitize_filename(original_base_name)

                yield f"状态：正在生成字幕文件 ({', '.join(output_formats)})...", None, ""

                generated_content_preview = "" # 用于在UI预览，默认只预览第一个格式（每个文件重置）

                if not os.path.exists(self.subtitles_folder_path):
                    os.makedirs(self.subtitles_folder_path, exist_ok=True)
                for fmt in output_formats:
                    try:

                        # 1. 获取规格：如果不在表里，就直接用 fmt 作为扩展名
                        suffix, ext = self.FORMAT_SPECS.get(fmt, ("", fmt))
                        # 2. 生成文件名：优雅地组合 base_name + 后缀 + 扩展名
                        output_filename = f"{base_name}{suffix}.{ext}"
                
                        content = self.subtitle_generator.generate_content(segment_timestamps, fmt)
                        output_path_for_download = os.path.join(self.subtitles_folder_path, output_filename)
                        with open(output_path_for_download, "w", encoding="utf-8") as subtitle_file:
                            subtitle_file.write(content)
                        output_files_all.append(output_path_for_download)

                        # 仅预览 SRT 或第一个格式
                        if fmt == "srt" or generated_content_preview == "":
                            generated_content_preview = content
                    except Exception as e:
                        logger.error(f"生成 {fmt} 格式失败: {e}")
                    logger.info(f"字幕文件位于: {output_path_for_download}")

            except Exception as e:
                logger.error(f"处理文件 {file_name} 时发生未知错误: {e}")
                import traceback
                traceback.print_exc()
                yield f"错误：处理文件 {file_name} 时发生未知错误: {e}。正在跳过此文件。", None, ""
                continue
            finally:
                if extracted_audio_path and os.path.exists(extracted_audio_path):
                    try:
                        os.remove(extracted_audio_path)
                    except OSError as e_clean:
                        logger.warning(f"无法删除临时音频文件 {extracted_audio_path}: {e_clean}")

        # 最终汇总放在循环外：即使最后一个文件失败被跳过，
        # 之前成功生成的字幕文件也能正常显示在下载列表中
        elapsed_time_total = time.time() - start_time_total
        status_message = f"处理完成。总耗时 {elapsed_time_total:.2f} 秒。生成{len(output_files_all)} 个字幕文件。"
        logger.info(status_message)
        yield status_message, output_files_all if output_files_all else None, generated_content_preview
    
    def create_zip_archive(self, file_objs: list) -> str:
        """将生成的文件打包成 ZIP"""
        if not file_objs:
            logger.warning("没有文件可打包")
            return None

        # 确保输出目录存在
        if not os.path.exists(self.subtitles_folder_path):
            os.makedirs(self.subtitles_folder_path, exist_ok=True)

        # 生成带时间戳的 ZIP 文件名
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        zip_filename = f"subtitles_package_{timestamp}.zip"
        zip_path = os.path.join(self.subtitles_folder_path, zip_filename)

        logger.info(f"开始打包 ZIP: {zip_path}")

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_obj in file_objs:
                    # Gradio 传回的文件对象通常是 NamedString 或具有 name 属性的对象
                    # 如果是路径字符串，直接使用；如果是对象，取 .name
                    file_path = file_obj.name if hasattr(file_obj, 'name') else file_obj
                    
                    if os.path.exists(file_path):
                        # arcname 确保 ZIP 内部不包含绝对路径，只包含文件名
                        zipf.write(file_path, arcname=os.path.basename(file_path))
                    else:
                        logger.warning(f"打包时文件未找到: {file_path}")
            
            logger.info(f"ZIP 打包成功: {zip_path}")
            return zip_path
        
        except Exception as e:
            logger.error(f"打包 ZIP 失败: {e}")
            import traceback
            traceback.print_exc()
            return None


    def _sanitize_filename(self, filename: str) -> str:
        # 替换 Windows/Linux 常见的非法字符
        return re.sub(r'[\\/*?:"<>|]', "_", filename)
    