"""系统核心接口、抽象基类与强类型数据结构定义模块。

定义应用内部服务、控制器、取消令牌以及标准字幕数据结构的契约。
"""

import threading
from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Any, TypedDict


class CharTimestampDict(TypedDict, total=False):
    """字符级时间戳字典结构。"""

    char: str
    start: float
    end: float


class WordTimestampDict(TypedDict, total=False):
    """词级时间戳字典结构。"""

    word: str
    start: float
    end: float


class SubtitleSegmentDict(TypedDict, total=False):
    """标准字幕段落数据字典结构。"""

    start: float
    end: float
    segment: str
    text: str
    index: int
    chars: list[CharTimestampDict]
    words: list[WordTimestampDict]


class CorrectionEntry(TypedDict):
    """校对本替换条目。"""

    error: str
    correct: str


class CancellationToken:
    """协作式取消令牌，用于在多线程与异步任务中安全、及时地响应取消请求。"""

    def __init__(self) -> None:
        """初始化取消令牌。"""
        self._is_cancelled = threading.Event()

    def cancel(self) -> None:
        """触发取消操作。"""
        self._is_cancelled.set()

    def reset(self) -> None:
        """重置取消状态。"""
        self._is_cancelled.clear()

    @property
    def is_cancelled(self) -> bool:
        """检查当前任务是否已被请求取消。

        Returns:
            bool: 如果已被取消则返回 True，否则返回 False。
        """
        return self._is_cancelled.is_set()

    def check_cancelled(self) -> None:
        """如果已取消则抛出 TaskCancelledError 异常。

        Raises:
            TaskCancelledError: 当任务被请求取消时抛出。
        """
        if self.is_cancelled:
            raise TaskCancelledError("任务已被用户取消。")


class TaskCancelledError(Exception):
    """当任务被协作式取消令牌中断时抛出。"""

    pass


class IASRService(ABC):
    """封装所有与 NeMo ASR 模型相关的操作。"""

    # 推理设备 (torch.device | Any)，UI 层用于显示 GPU/CPU 状态
    device: Any

    @property
    @abstractmethod
    def is_model_loaded(self) -> bool:
        """检查 ASR 模型是否已加载。

        Returns:
            bool: 模型已加载返回 True，否则返回 False。
        """
        ...

    @abstractmethod
    def load_model_from_ngc(self, model_name: str) -> str:
        """从 NVIDIA NGC 加载预训练模型。

        Args:
            model_name (str): NGC 上的模型标识符。

        Returns:
            str: 操作状态描述文本。
        """
        ...

    @abstractmethod
    def load_model_from_local(self, model_path: str) -> str:
        """从本地 .nemo 文件加载模型。

        Args:
            model_path (str): 本地 .nemo 文件路径。

        Returns:
            str: 操作状态描述文本。
        """
        ...

    @abstractmethod
    def transcribe_audio_in_chunks(
        self,
        audio_path: str,
        chunk_length_ms: int,
        max_chars: int = 0,
        cancellation_token: CancellationToken | None = None,
    ) -> list[SubtitleSegmentDict]:
        """将音频文件分块转录并返回带有全局时间戳的段列表。

        Args:
            audio_path (str): 音频文件路径 (WAV 格式)。
            chunk_length_ms (int): 每块的长度（毫秒）。
            max_chars (int): 单句最大长度限制，0 表示不限制。
            cancellation_token (CancellationToken | None): 协作式取消令牌。

        Returns:
            list[SubtitleSegmentDict]: 包含 start, end, segment, chars, words 等字段的段落列表。
        """
        ...


class IConfigManager(ABC):
    """定义配置管理器的接口，封装配置的加载、保存和访问功能。"""

    @abstractmethod
    def get_config_all(self) -> dict[str, Any]:
        """获取所有配置项。

        Returns:
            dict[str, Any]: 包含所有配置键值的字典副本。
        """
        ...

    @abstractmethod
    def save_config(self, **kwargs: Any) -> None:
        """保存配置到配置文件。

        Args:
            **kwargs: 键值对配置项。
        """
        ...

    @abstractmethod
    def get_config_value(self, key: str) -> Any:
        """获取配置中的特定值。

        Args:
            key (str): 配置项名称。

        Returns:
            Any: 配置项对应的值。
        """
        ...


class ISubtitleGenerator(ABC):
    """字幕生成与解析服务接口。"""

    @abstractmethod
    def generate_content(
        self, segment_timestamps: list[SubtitleSegmentDict] | list[dict[str, Any]], format_type: str
    ) -> str:
        """根据时间戳列表生成指定格式的字幕内容。

        Args:
            segment_timestamps (list[SubtitleSegmentDict] | list[dict[str, Any]]): 字幕段落列表。
            format_type (str): 格式类型 (e.g., 'srt', 'vtt', 'txt', 'json', 'lrc', 'ass')。

        Returns:
            str: 格式化后的字幕文本。
        """
        ...

    @abstractmethod
    def format_time(self, seconds: float, separator: str = ",") -> str:
        """将秒格式化为 HH:MM:SS,mmm 字符串（公开 API，供编辑器等复用）。

        Args:
            seconds (float): 时间秒数。
            separator (str): 毫秒分隔符（默认为逗号 ','，VTT 可指定为 '.'）。

        Returns:
            str: 格式化后的时间戳字符串。
        """
        ...

    @abstractmethod
    def srt_time_to_seconds(self, time_str: str) -> float:
        """将 SRT 时间字符串 (00:00:00,000) 转换为秒。

        Args:
            time_str (str): SRT 格式时间字符串。

        Returns:
            float: 对应的秒数。
        """
        ...

    @abstractmethod
    def parse_srt(self, srt_content: str) -> list[SubtitleSegmentDict]:
        """解析 SRT 字幕内容为时间戳列表。

        Args:
            srt_content (str): SRT 格式的字幕内容字符串。

        Returns:
            list[SubtitleSegmentDict]: 解析后的段落字典列表。
        """
        ...


class IAudioService(ABC):
    """定义音频处理服务的接口，封装音频提取与预处理。"""

    @abstractmethod
    def extract_audio_from_video(self, input_media_path: str) -> str | None:
        """使用 ffmpeg 从视频文件中提取音频并转换为 WAV 格式。

        Args:
            input_media_path (str): 待提取的媒体文件路径。

        Returns:
            str | None: 提取成功的音频路径，失败时返回 None。
        """
        ...


class IModelController(ABC):
    """专门处理模型相关 UI 事件的控制器接口。"""

    @abstractmethod
    def handle_load_local_click(
        self, path_from_input_box: str, chunk_val_from_slider: int, selected_cloud_model: str
    ) -> str:
        """处理“加载本地模型”按钮点击事件。

        Args:
            path_from_input_box (str): 用户输入的本地模型路径。
            chunk_val_from_slider (int): 切片长度滑块值（秒）。
            selected_cloud_model (str): 当前选中的云端模型名称。

        Returns:
            str: 加载状态消息。
        """
        ...

    @abstractmethod
    def handle_load_cloud_click(self, chunk_val_from_slider: int, selected_cloud_model: str) -> str:
        """处理“加载云端模型”按钮点击事件。

        Args:
            chunk_val_from_slider (int): 切片长度滑块值（秒）。
            selected_cloud_model (str): 当前选中的云端模型名称。

        Returns:
            str: 加载状态消息。
        """
        ...


class ITranscriptionController(ABC):
    """专门处理转录相关 UI 事件的控制器接口。"""

    @abstractmethod
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
            media_file_objs (list[Any]): 上传的视频/音频文件对象列表。
            chunk_length_s (int): 音频分块长度（秒）。
            output_formats (list[str]): 输出字幕格式列表 (e.g., ['srt', 'vtt'])。
            word_output_formats (list[str]): 逐词/逐字级额外输出格式列表。
            enable_split (bool): 是否启用长字幕拆分。
            max_chars (int): 拆分时每条字幕的最大字符数。

        Yields:
            tuple[str, list[str] | None, str]: 状态消息, 输出字幕文件路径列表, 字幕内容预览。
        """
        ...

    @abstractmethod
    def create_zip_archive(self, file_objs: list[Any]) -> str | None:
        """将列表中的文件打包成 ZIP 文件。

        Args:
            file_objs (list[Any]): 文件对象列表。

        Returns:
            str | None: 生成的 ZIP 文件路径，失败时返回 None。
        """
        ...


class ISubtitleEditorController(ABC):
    """字幕编辑与校对控制器接口。"""

    @abstractmethod
    def load_subtitle_file(self, file_objs: list[Any]) -> tuple[list[list[Any]] | None, str]:
        """加载字幕文件并解析为表格数据。

        Args:
            file_objs (list[Any]): 上传的文件对象列表。

        Returns:
            tuple[list[list[Any]] | None, str]: (表格数据列表, 状态提示文本)。
        """
        ...

    @abstractmethod
    def apply_batch_corrections(self, subtitle_data: Any, correction_table: Any) -> list[list[Any]]:
        """应用校对本中的批量替换逻辑。

        Args:
            subtitle_data (Any): 待替换的字幕表格数据。
            correction_table (Any): 校对规则表格数据。

        Returns:
            list[list[Any]]: 批量替换后的字幕数据列表。
        """
        ...

    @abstractmethod
    def save_subtitles(self, subtitle_data: Any, original_file_obj: Any) -> str | None:
        """将表格数据保存回字幕文件。

        Args:
            subtitle_data (Any): 编辑表格数据 (DataFrame 或 list)。
            original_file_obj (Any): 原始上传文件对象（或对象列表），用于推导输出文件名。

        Returns:
            str | None: 保存后的文件路径，失败时返回 None。
        """
        ...

    @abstractmethod
    def load_corrections(self) -> list[list[str]]:
        """从本地加载校对本数据。

        Returns:
            list[list[str]]: 校对规则列表。
        """
        ...

    @abstractmethod
    def save_corrections(self, correction_table_data: Any) -> None:
        """保存校对本数据到本地。

        Args:
            correction_table_data (Any): 校对本规则数据。
        """
        ...


class ITranslationService(ABC):
    """大模型翻译与智能断句服务接口。"""

    @abstractmethod
    async def translate_segments(
        self,
        segments: list[SubtitleSegmentDict] | list[dict[str, Any]],
        target_lang: str,
        api_key: str,
        base_url: str,
        model: str,
        is_bilingual: bool,
        proxy: str | None = None,
        concurrency: int = 5,
        chunk_size: int = 30,
    ) -> list[SubtitleSegmentDict]:
        """调用大模型并发翻译字幕段落。

        Args:
            segments (list[SubtitleSegmentDict] | list[dict[str, Any]]): 原始字幕段落列表。
            target_lang (str): 目标翻译语言。
            api_key (str): API 密钥。
            base_url (str): API 基础 URL。
            model (str): 模型名称。
            is_bilingual (bool): 是否保留双语字幕。
            proxy (str | None): 代理地址。
            concurrency (int): 并发数。
            chunk_size (int): 批次大小。

        Returns:
            list[SubtitleSegmentDict]: 翻译后的字幕段落列表。
        """
        ...

    @abstractmethod
    async def segment_subtitles(
        self,
        segments: list[SubtitleSegmentDict] | list[dict[str, Any]],
        api_key: str,
        base_url: str,
        model: str,
        proxy: str | None = None,
        concurrency: int = 3,
        chunk_size: int = 50,
    ) -> list[SubtitleSegmentDict]:
        """调用大模型进行智能断句与时间戳重对齐。

        Args:
            segments (list[SubtitleSegmentDict] | list[dict[str, Any]]): 原始字幕段落列表。
            api_key (str): API 密钥。
            base_url (str): API 基础 URL。
            model (str): 模型名称。
            proxy (str | None): 代理地址。
            concurrency (int): 并发数。
            chunk_size (int): 批次大小。

        Returns:
            list[SubtitleSegmentDict]: 重构断句与对齐后的字幕段落列表。
        """
        ...


class ITranslationController(ABC):
    """处理翻译与智能断句 UI 事件的控制器接口。"""

    @abstractmethod
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
        """处理翻译 UI 事件。

        Args:
            file_objs (list[Any]): 上传的文件列表。
            target_lang (str): 目标语言。
            is_bilingual (bool): 是否双语。
            api_key (str): API 密钥。
            base_url (str): API 基础 URL。
            model_name (str): 模型标识。
            proxy (str | None): 代理地址。
            concurrency (int): 并发任务数。
            chunk_size (int): 批次大小。

        Returns:
            tuple[str, list[str] | None, str]: 状态消息, 翻译后文件路径列表, 内容预览。
        """
        ...

    @abstractmethod
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
        """处理 AI 断句 UI 事件。

        Args:
            file_objs (list[Any]): 上传的文件列表。
            api_key (str): API 密钥。
            base_url (str): API 基础 URL。
            model_name (str): 模型标识。
            proxy (str | None): 代理地址。
            concurrency (int): 并发任务数。
            chunk_size (int): 批次大小。

        Returns:
            tuple[str, list[str] | None]: 状态消息, 断句后文件路径列表。
        """
        ...


class IApplication(ABC):
    """定义应用程序的接口，封装核心服务和配置管理器。"""

    @property
    @abstractmethod
    def asr_service(self) -> IASRService:
        """获取 ASR 服务实例。

        Returns:
            IASRService: ASR 语音识别服务。
        """
        ...

    @property
    @abstractmethod
    def config_manager(self) -> IConfigManager:
        """获取配置管理器实例。

        Returns:
            IConfigManager: 配置管理器。
        """
        ...

    @property
    @abstractmethod
    def audio_service(self) -> IAudioService:
        """获取音频处理服务实例。

        Returns:
            IAudioService: 音频处理服务。
        """
        ...

    @property
    @abstractmethod
    def subtitle_generator(self) -> ISubtitleGenerator:
        """获取字幕生成服务实例。

        Returns:
            ISubtitleGenerator: 字幕生成服务。
        """
        ...

    @property
    @abstractmethod
    def model_controller(self) -> IModelController:
        """获取模型控制器实例。

        Returns:
            IModelController: 模型控制器。
        """
        ...

    @property
    @abstractmethod
    def transcription_controller(self) -> ITranscriptionController:
        """获取转录控制器实例。

        Returns:
            ITranscriptionController: 转录控制器。
        """
        ...

    @property
    @abstractmethod
    def subtitle_editor_controller(self) -> ISubtitleEditorController:
        """获取字幕编辑控制器实例。

        Returns:
            ISubtitleEditorController: 字幕编辑控制器。
        """
        ...

    @property
    @abstractmethod
    def translation_controller(self) -> ITranslationController:
        """获取翻译控制器实例。

        Returns:
            ITranslationController: 翻译控制器。
        """
        ...
