from abc import ABC, abstractmethod
from typing import Any


class IASRService(ABC):
    """
    封装所有与 NeMo ASR 模型相关的操作。
    """

    # 推理设备 (torch.device)，UI 层用于显示 GPU/CPU 状态
    device: Any

    @property
    @abstractmethod
    def is_model_loaded(self) -> bool:
        """检查 ASR 模型是否已加载。"""
        ...

    @abstractmethod
    def load_model_from_ngc(self, model_name: str) -> str:
        """从 NVIDIA NGC 加载预训练模型。"""
        ...

    @abstractmethod
    def load_model_from_local(self, model_path: str) -> str:
        """从本地 .nemo 文件加载模型。"""
        ...

    @abstractmethod
    def transcribe_audio_in_chunks(
        self, audio_path: str, chunk_length_ms: int, max_chars: int = 0
    ) -> list:
        """
        将音频文件分块转录并返回带有全局时间戳的段列表。
        ARGS:
            audio_path: 音频文件路径 (假设为 WAV)。
            chunk_length_ms: 每块的长度（毫秒）。
            max_chars: 单句最大长度限制，0 表示不限制
        RETURNS:
            包含 {'start': float, 'end': float, 'segment': str} 的列表。

        """
        ...


class IConfigManager(ABC):
    """
    定义配置管理器的接口，封装配置的加载、保存和访问功能。
    """

    @abstractmethod
    def get_config_all(self) -> dict:
        """
        获取所有配置项。
        返回包含所有配置项的字典。
        """
        ...

    @abstractmethod
    def save_config(self, **kwargs) -> None:
        """
        保存配置到 config.json 文件。
        :param kwargs: 接受以下关键字参数:
        - local_model_path (str): 本地模型路径
        - chunk_length_s (int): 分块长度（秒）
        - cloud_model_name (str): 云端模型名称
        - language (str): 界面语言
        """
        ...

    @abstractmethod
    def get_config_value(self, key: str):
        """获取配置中的特定值。"""
        ...


class ISubtitleGenerator(ABC):
    """
    字幕生成服务接口。
    支持多种格式转换逻辑
    """

    @abstractmethod
    def generate_content(self, segment_timestamps: list, format_type: str) -> str:
        """
        根据时间戳列表生成指定格式的字幕内容。
        ARGS:
            segment_timestamps: 包含 {'start': float, 'end': float, 'segment': str} 的列表。
            format_type: 格式类型 (e.g., 'srt', 'vtt', 'txt', 'json')
        RETURNS:
            SRT 格式的字符串。
        """
        ...

    @abstractmethod
    def format_time(self, seconds: float, separator: str = ",") -> float | str:
        """将秒格式化为 HH:MM:SS,mmm 字符串（公开 API，供编辑器等复用）"""
        ...

    @abstractmethod
    def srt_time_to_seconds(self, time_str: str) -> float:
        """将 SRT 时间字符串 (00:00:00,000) 转换为秒（公开 API）"""
        ...

    @abstractmethod
    def parse_srt(self, srt_content: str) -> list:
        """
        解析 SRT 字幕内容为时间戳列表。
        ARGS:
            srt_content: SRT 格式的字幕内容字符串。
        RETURNS:
            包含 {'start': float, 'end': float, 'segment': str} 的列表。
        """
        ...


class IAudioService(ABC):
    """
    定义音频处理服务的接口，封装音频相关的核心服务。
    """

    @abstractmethod
    def extract_audio_from_video(self, input_media_path: str) -> str | None:
        """
        使用 ffmpeg 从视频文件中提取音频并转换为 WAV 格式。
        返回提取的音频文件路径，或在失败时返回 None。
        """
        ...


class IModelController(ABC):
    """
    一个专门处理模型相关 UI 事件的控制器

    """

    @abstractmethod
    def handle_load_local_click(
        self, path_from_input_box, chunk_val_from_slider, selected_cloud_model
    ):
        """处理“加载本地模型”按钮点击事件。"""
        ...

    @abstractmethod
    def handle_load_cloud_click(self, chunk_val_from_slider, selected_cloud_model):
        """处理“加载云端模型”按钮点击事件。"""
        ...


class ITranscriptionController(ABC):
    """
    一个专门处理转录相关 UI 事件的控制器。
    """

    @abstractmethod
    def process_media(
        self,
        media_file_objs: list,
        chunk_length_s: int,
        output_formats: list,
        word_output_formats: list,
        enable_split: bool = False,
        max_chars: int = 0,
    ):
        """处理上传的视频/音频文件，生成字幕文件。
        ARGS:
            media_file_objs: Gradio 上传的视频/音频文件对象列表。
            chunk_length_s: 音频分块长度（秒）。
            output_formats: 输出字幕格式列表 (e.g., ['srt', 'vtt'])
            word_output_formats: 逐词/逐字级额外输出格式列表 (e.g., ['word_srt'])
            enable_split: 是否启用长字幕拆分。
            max_chars: 拆分时每条字幕的最大字符数。
        YIELDS:
            状态消息 (str), 输出字幕文件路径列表 (list), 字幕内容预览 (str)。
        """
        ...

    @abstractmethod
    def create_zip_archive(self, file_objs: list) -> str | None:
        """
        将列表中的文件打包成 ZIP 文件。
        ARGS:
            file_objs: Gradio 文件对象列表 (包含 .name 路径属性)
        RETURNS:
            生成的 ZIP 文件路径 (str)，失败时返回 None
        """
        ...


class ISubtitleEditorController(ABC):
    @abstractmethod
    def load_subtitle_file(self, file_objs: list):
        """加载字幕文件并解析为表格数据"""
        ...

    @abstractmethod
    def apply_batch_corrections(self, subtitle_data, correction_table):
        """应用校对本中的批量替换逻辑"""
        ...

    @abstractmethod
    def save_subtitles(self, subtitle_data, original_file_obj):
        """将表格数据保存回字幕文件。
        ARGS:
            subtitle_data: 编辑表格数据 (DataFrame 或 list)。
            original_file_obj: 原始上传文件对象（或对象列表），用于推导输出文件名。
        RETURNS:
            保存后的文件路径 (str)，失败时返回 None。
        """
        ...

    @abstractmethod
    def load_corrections(self) -> list:
        """从本地加载校对本数据"""
        ...

    @abstractmethod
    def save_corrections(self, correction_table_data) -> None:
        """保存校对本数据到本地"""
        ...


class ITranslationService(ABC):
    @abstractmethod
    async def translate_segments(
        self,
        segments: list,
        target_lang: str,
        api_key: str,
        base_url: str,
        model: str,
        is_bilingual: bool,
        proxy: str | None = None,
        concurrency: int = 5,
        chunk_size: int = 30,
    ) -> list:
        """调用大模型翻译字幕段落"""
        ...

    @abstractmethod
    async def segment_subtitles(
        self,
        segments: list,
        api_key: str,
        base_url: str,
        model: str,
        proxy: str | None = None,
        concurrency: int = 3,
        chunk_size: int = 50,
    ) -> list:
        """调用大模型进行智能断句"""
        ...


class ITranslationController(ABC):
    @abstractmethod
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
        """处理翻译 UI 事件。
        RETURNS:
            (状态消息 str, 翻译后文件路径列表 list, 内容预览 str)
        """
        ...

    @abstractmethod
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
        """处理 AI 断句 UI 事件。
        RETURNS:
            (状态消息 str, 断句后文件路径列表 list)
        """
        ...


class IApplication(ABC):
    """
    定义应用程序的接口，封装核心服务和配置管理器。
    """

    @property
    @abstractmethod
    def asr_service(self) -> IASRService:
        """获取 ASR 服务实例。"""
        ...

    @property
    @abstractmethod
    def config_manager(self) -> IConfigManager:
        """获取配置管理器实例。"""
        ...

    @property
    @abstractmethod
    def audio_service(self) -> IAudioService:
        """获取音频处理服务实例。"""
        ...

    @property
    @abstractmethod
    def subtitle_generator(self) -> ISubtitleGenerator:
        """获取字幕生成服务实例。"""
        ...

    @property
    @abstractmethod
    def model_controller(self) -> IModelController:
        """获取模型控制器实例。"""
        ...

    @property
    @abstractmethod
    def transcription_controller(self) -> ITranscriptionController:
        """获取转录控制器实例。"""
        ...

    @property
    @abstractmethod
    def subtitle_editor_controller(self) -> ISubtitleEditorController:
        """获取字幕编辑控制器实例。"""
        ...

    @property
    @abstractmethod
    def translation_controller(self) -> ITranslationController:
        """获取翻译控制器实例。"""
        ...
