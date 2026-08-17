
import os
import subprocess
import tempfile

from interfaces import IAudioService
from utils.exceptions import AudioProcessingError
from utils.logger import logger


class AudioService(IAudioService):
    """负责所有与音频提取和预处理相关的操作。"""

    def __init__(self) -> None:
        """初始化 AudioService 并执行 FFmpeg 可用性软检测。"""
        self.is_ffmpeg_available: bool = self._check_ffmpeg(raise_error=False)

    def _check_ffmpeg(self, raise_error: bool = False) -> bool:
        """检查系统中是否安装并可用 ffmpeg。

        Args:
            raise_error (bool): 当检测失败时是否主动抛出 AudioProcessingError。默认为 False。

        Returns:
            bool: FFmpeg 是否在系统中可用。

        Raises:
            AudioProcessingError: 当 raise_error 为 True 且 FFmpeg 不可用时抛出。
        """
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                check=True,
                capture_output=True,
                encoding="utf-8",
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning(
                "警告：ffmpeg 未检测到或未正确安装。请安装 ffmpeg 并确保其在系统 PATH 中。"
            )
            if raise_error:
                raise AudioProcessingError("FFmpeg 未安装或不可用。") from None
            return False

    def extract_audio_from_video(self, input_media_path: str) -> str | None:
        """使用 ffmpeg 从视频文件中提取音频并转换为 16kHz 单声道 WAV 格式。

        Args:
            input_media_path (str): 待提取音频的输入视频或媒体文件路径。

        Returns:
            str | None: 提取成功的临时 WAV 音频文件路径，或在失败时返回 None。

        Raises:
            AudioProcessingError: 当 FFmpeg 不可用或执行提取命令失败时抛出。
        """
        if not self.is_ffmpeg_available and not self._check_ffmpeg(raise_error=False):
            raise AudioProcessingError("FFmpeg 未安装或不可用，请安装 ffmpeg 并确保其在系统 PATH 中。")

        temp_audio_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_audio_path = temp_audio_file.name
        temp_audio_file.close()

        ffmpeg_command = [
            "ffmpeg",
            "-i",
            input_media_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-y",
            output_audio_path,
        ]
        try:
            subprocess.run(
                ffmpeg_command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            logger.info(f"音频提取成功到: {output_audio_path}")
            if os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 0:
                return output_audio_path

            if os.path.exists(output_audio_path):
                os.remove(output_audio_path)  # 清理空文件
                logger.error("FFmpeg 提取的音频文件为空。")
            return None
        except subprocess.CalledProcessError as e:
            if os.path.exists(output_audio_path):
                os.remove(output_audio_path)
            raise AudioProcessingError(f"FFmpeg 提取音频失败: {e.stderr}") from e
        except FileNotFoundError as e:
            if os.path.exists(output_audio_path):
                os.remove(output_audio_path)
            raise AudioProcessingError("FFmpeg 未找到，请确保已安装") from e


