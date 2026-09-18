"""NeMo ASR 语音识别模型服务模块。

封装 NeMo 模型加载、GPU/CPU 显存管理、多线程并发安全保护以及内存音频张量分块推理。
"""

import gc
import os
import tempfile
import threading
from typing import Any

import numpy as np
import torch
from pydub import AudioSegment

try:
    import nemo.collections.asr as nemo_asr
except Exception:
    nemo_asr = None  # type: ignore[assignment]

from core.constants import (
    AUDIO_NORM_FACTOR,
    DEFAULT_AUDIO_CHANNELS,
    DEFAULT_SAMPLE_RATE,
    MS_PER_SECOND,
)
from core.post_processors import (
    DefaultSegmentStrategy,
    ITranscriptionStrategy,
    JapaneseCharStrategy,
)
from interfaces import CancellationToken, IASRService, SubtitleSegmentDict
from utils.logger import logger


class ASRService(IASRService):
    """封装所有与 NeMo ASR 模型相关的操作，提供线程安全的模型加载与转录服务。"""

    def __init__(self) -> None:
        """初始化 ASRService，分配硬件设备并创建可重入互斥锁。"""
        self._lock: threading.RLock = threading.RLock()
        self.model: Any = None
        self.device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # 当前使用的处理策略，默认为普通策略
        self.processor_strategy: ITranscriptionStrategy = DefaultSegmentStrategy()
        logger.info(f"ASRService 初始化，使用设备: {self.device}")

    @property
    def is_model_loaded(self) -> bool:
        """检查 ASR 模型是否已加载。

        Returns:
            bool: 如果当前持有已加载的模型实例返回 True，否则返回 False。
        """
        with self._lock:
            return self.model is not None

    def _ensure_nemo(self) -> bool:
        """确保 NeMo ASR 模块已就绪。

        Returns:
            bool: NeMo ASR 模块是否可用。
        """
        global nemo_asr
        if nemo_asr is None:
            try:
                import builtins
                import sys

                if sys.platform.startswith("win"):
                    _orig_open = builtins.open

                    def _safe_open(*args: Any, **kwargs: Any) -> Any:
                        """在 Windows 平台下为 open() 注入默认 UTF-8 编码。

                        Args:
                            *args (Any): 位置参数。
                            **kwargs (Any): 关键字参数。

                        Returns:
                            Any: 打开的文件对象。
                        """
                        mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
                        if "b" not in str(mode) and "encoding" not in kwargs:
                            kwargs["encoding"] = "utf-8"
                        return _orig_open(*args, **kwargs)

                    builtins.open = _safe_open

                import nemo.collections.asr as imported_nemo_asr

                nemo_asr = imported_nemo_asr
            except Exception as e:
                logger.error(f"导入 NeMo ASR 模块失败: {e}")
                return False
        return True

    def _release_memory(self) -> None:
        """释放当前模型占用的显存和系统内存（线程安全）。"""
        with self._lock:
            if self.model is not None:
                logger.info("释放当前模型占用的显存和内存...")
                try:
                    if hasattr(self.model, "to"):
                        try:
                            self.model.to("cpu")
                        except Exception:
                            pass
                finally:
                    self.model = None
                    gc.collect()
                    if torch.cuda.is_available():
                        try:
                            torch.cuda.empty_cache()
                            torch.cuda.ipc_collect()
                        except Exception:
                            pass
                logger.info("旧模型显存释放完成。")

    def _update_strategy(self, model_name: str) -> None:
        """根据模型名称决定使用哪个处理策略。

        Args:
            model_name (str): 加载的模型名称或路径。
        """
        name_lower = model_name.lower()

        if "ja" in name_lower or "japanese" in name_lower:
            logger.info(f"模型 '{model_name}' 被识别为日语模型，切换至 [日语字符重组策略]。")
            self.processor_strategy = JapaneseCharStrategy()
        else:
            logger.info(f"模型 '{model_name}' 被识别为通用模型，切换至 [默认段落策略]。")
            self.processor_strategy = DefaultSegmentStrategy()

    def load_model_from_ngc(self, model_name: str) -> str:
        """从 NVIDIA NGC 加载预训练模型（线程安全）。

        Args:
            model_name (str): NGC 上的模型标识符。

        Returns:
            str: 操作结果提示文本。
        """
        with self._lock:
            if not self._ensure_nemo():
                return f"从NGC加载云端模型 '{model_name}' 失败: NeMo 依赖不可用。"

            # 释放当前模型占用的显存和内存
            self._release_memory()
            try:
                self.model = nemo_asr.models.ASRModel.from_pretrained(
                    model_name=model_name, map_location=self.device
                )
                # 加载成功后，更新策略
                self._update_strategy(model_name)
                return f"云端模型 '{model_name}' 加载成功。"
            except Exception as e:
                self.model = None
                return f"从NGC加载云端模型 '{model_name}' 失败: {e}"

    def load_model_from_local(self, model_path: str) -> str:
        """从本地 .nemo 文件加载模型（线程安全）。

        Args:
            model_path (str): 本地 .nemo 文件路径。

        Returns:
            str: 操作结果提示文本。
        """
        with self._lock:
            if not self._ensure_nemo():
                return f"从本地路径加载模型 '{model_path}' 失败: NeMo 依赖不可用。"

            # 释放当前模型占用的显存和内存
            self._release_memory()
            actual_path = model_path.strip()
            if not os.path.exists(actual_path) or not actual_path.endswith(".nemo"):
                return f"错误：指定的本地模型路径无效: {actual_path}"

            logger.info(f"尝试从本地路径加载模型: {actual_path}...")
            try:
                self.model = nemo_asr.models.ASRModel.restore_from(
                    restore_path=actual_path, map_location=self.device
                )
                model_name = os.path.basename(actual_path)
                # 加载成功后，更新策略
                self._update_strategy(model_name)
                return f"本地模型 '{model_name}' 加载成功。"
            except Exception as e:
                self.model = None
                logger.error(f"从本地路径加载模型失败: {e}")
                return f"从本地路径加载模型 '{actual_path}' 失败: {e}"

    def transcribe_audio_in_chunks(
        self,
        audio_path: str,
        chunk_length_ms: int,
        max_chars: int = 0,
        cancellation_token: CancellationToken | None = None,
    ) -> list[SubtitleSegmentDict]:
        """将音频文件分块转录并返回带有全局时间戳的段列表（线程安全与内存张量优化）。

        Args:
            audio_path (str): 待转录的音频文件路径 (WAV 格式)。
            chunk_length_ms (int): 每个音频块的切片长度（毫秒）。
            max_chars (int): 单句最大字符长度限制，0 表示不限制。
            cancellation_token (CancellationToken | None): 协作式取消令牌。

        Returns:
            list[SubtitleSegmentDict]: 包含 start, end, segment, chars, words 等字段的段落列表。
        """
        with self._lock:
            if not self.is_model_loaded:
                logger.error("错误: ASR 模型未加载，无法进行转录。")
                return []

            if not audio_path or not os.path.exists(audio_path):
                logger.error(f"错误: 音频文件路径 '{audio_path}' 无效或文件不存在。")
                return []

            logger.info(f"正在加载音频文件 '{audio_path}' 进行分块处理...")
            try:
                audio = AudioSegment.from_wav(audio_path)
                audio = audio.set_frame_rate(DEFAULT_SAMPLE_RATE).set_channels(
                    DEFAULT_AUDIO_CHANNELS
                )
            except Exception as e:
                logger.error(f"加载或处理音频文件 '{audio_path}' 时发生错误 (pydub): {e}")
                return []

            audio_duration_ms = len(audio)
            logger.info(f"音频总时长: {audio_duration_ms / MS_PER_SECOND:.2f} 秒")
            all_results: list[SubtitleSegmentDict] = []

            for i in range(0, audio_duration_ms, chunk_length_ms):
                if cancellation_token and cancellation_token.is_cancelled:
                    logger.info("转录任务已被协作式取消令牌中断，提前退出分块循环。")
                    break

                start_time_ms = i
                end_time_ms = min(i + chunk_length_ms, audio_duration_ms)
                chunk = audio[start_time_ms:end_time_ms]

                logger.info(
                    f"处理音频块: {start_time_ms / MS_PER_SECOND:.2f}s - {end_time_ms / MS_PER_SECOND:.2f}s"
                )

                chunk_output_list = None
                temp_chunk_file_path = ""
                try:
                    # 1. 优先尝试内存张量直传推理（避免磁盘 I/O 抖动）
                    try:
                        raw_samples = (
                            np.frombuffer(chunk.raw_data, dtype=np.int16).astype(
                                np.float32
                            )
                            / AUDIO_NORM_FACTOR
                        )
                        chunk_tensor = torch.from_numpy(raw_samples)
                        chunk_output_list = self.model.transcribe(
                            audio=[chunk_tensor],
                            batch_size=1,
                            timestamps=True,
                            return_hypotheses=True,
                        )
                    except (
                        TypeError,
                        AttributeError,
                        NotImplementedError,
                        Exception,
                    ) as in_memory_err:
                        logger.debug(
                            f"内存张量直传推理未被底层模型支持 ({in_memory_err})，降级为临时磁盘 WAV 模式。"
                        )
                        chunk_output_list = None

                    # 2. 降级方案：若内存直传不可用或异常，使用临时 WAV 文件
                    if chunk_output_list is None:
                        with tempfile.NamedTemporaryFile(
                            suffix=".wav", delete=False
                        ) as temp_chunk_file:
                            temp_chunk_file_path = temp_chunk_file.name
                        chunk.export(temp_chunk_file_path, format="wav")

                        chunk_output_list = self.model.transcribe(
                            [temp_chunk_file_path],
                            batch_size=1,
                            timestamps=True,
                            return_hypotheses=True,
                        )

                    chunk_global_start_offset_sec = start_time_ms / float(MS_PER_SECOND)

                    new_segments = self.processor_strategy.process(
                        chunk_output_list,
                        chunk_global_start_offset_sec,
                        max_chars=max_chars,
                    )

                    if new_segments:
                        all_results.extend(new_segments)

                except Exception as e:
                    logger.error(
                        f"转录音频块 ({start_time_ms / MS_PER_SECOND:.2f}s - {end_time_ms / MS_PER_SECOND:.2f}s) 时发生错误: {e}",
                        exc_info=True,
                    )
                finally:
                    if temp_chunk_file_path and os.path.exists(temp_chunk_file_path):
                        try:
                            os.remove(temp_chunk_file_path)
                        except OSError as e_os:
                            logger.error(
                                f"删除临时音频文件 '{temp_chunk_file_path}' 时发生OS错误: {e_os}"
                            )

            all_results.sort(key=lambda x: float(x.get("start", 0.0)))
            return all_results
