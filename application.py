"""应用程序顶层装配与生命周期管理模块。

初始化并组装 ASR、音频提取、字幕生成、翻译与相关控制器，并驱动 Gradio UI 启动。
"""

from app_ui import create_ui
from controllers.model_controller import ModelController
from controllers.subtitle_editor_controller import SubtitleEditorController
from controllers.transcription_controller import TranscriptionController
from controllers.translation_controller import TranslationController
from core.translation_service import TranslationService
from interfaces import (
    IApplication,
    IASRService,
    IAudioService,
    IConfigManager,
    ISubtitleGenerator,
)


class Application(IApplication):
    """封装应用的所有状态和核心服务，并协调各个控制器。"""

    def __init__(
        self,
        config_manager: IConfigManager | None = None,
        asr_service: IASRService | None = None,
        audio_service: IAudioService | None = None,
        subtitle_generator: ISubtitleGenerator | None = None,
    ) -> None:
        """初始化应用程序并装配所有服务与控制器。

        Args:
            config_manager (IConfigManager | None): 配置管理器实例。为 None 时创建默认实例。
            asr_service (IASRService | None): ASR 模型识别服务实例。为 None 时创建默认实例。
            audio_service (IAudioService | None): 音频提取服务实例。为 None 时创建默认实例。
            subtitle_generator (ISubtitleGenerator | None): 字幕生成服务实例。为 None 时创建默认实例。
        """
        # 初始化核心服务（支持无参缺省构建）
        if config_manager is None:
            from utils.config_manager import ConfigManager

            config_manager = ConfigManager()
        if asr_service is None:
            from core.asr_service import ASRService

            asr_service = ASRService()
        if audio_service is None:
            from core.audio_processor import AudioService

            audio_service = AudioService()
        if subtitle_generator is None:
            from core.subtitle_generator import SubtitleService

            subtitle_generator = SubtitleService()

        self._config_manager: IConfigManager = config_manager
        self._asr_service: IASRService = asr_service
        self._audio_service: IAudioService = audio_service
        self._subtitle_service: ISubtitleGenerator = subtitle_generator

        # 初始化控制器
        self._model_controller: ModelController = ModelController(
            app_services=self._asr_service, config=self._config_manager
        )
        self._transcription_controller: TranscriptionController = TranscriptionController(
            app_services=self._asr_service,
            audio_service=self._audio_service,
            subtitle_generator=self._subtitle_service,
        )

        self._subtitle_editor_controller: SubtitleEditorController = SubtitleEditorController(
            subtitle_service=self._subtitle_service
        )

        self._translation_service: TranslationService = TranslationService()
        self._translation_controller: TranslationController = TranslationController(
            subtitle_service=self._subtitle_service,
            translation_service=self._translation_service,
            config_manager=self._config_manager,
        )

    @property
    def asr_service(self) -> IASRService:
        """获取 ASR 服务实例。

        Returns:
            IASRService: ASR 服务接口实例。
        """
        return self._asr_service

    @property
    def config_manager(self) -> IConfigManager:
        """获取配置管理器实例。

        Returns:
            IConfigManager: 配置管理器实例。
        """
        return self._config_manager

    @property
    def audio_service(self) -> IAudioService:
        """获取音频处理服务实例。

        Returns:
            IAudioService: 音频处理服务实例。
        """
        return self._audio_service

    @property
    def subtitle_generator(self) -> ISubtitleGenerator:
        """获取字幕生成服务实例。

        Returns:
            ISubtitleGenerator: 字幕生成服务实例。
        """
        return self._subtitle_service

    @property
    def model_controller(self) -> ModelController:
        """获取模型控制器实例。

        Returns:
            ModelController: 模型控制器实例。
        """
        return self._model_controller

    @property
    def transcription_controller(self) -> TranscriptionController:
        """获取转录控制器实例。

        Returns:
            TranscriptionController: 转录控制器实例。
        """
        return self._transcription_controller

    @property
    def subtitle_editor_controller(self) -> SubtitleEditorController:
        """获取字幕编辑控制器实例。

        Returns:
            SubtitleEditorController: 字幕编辑控制器实例。
        """
        return self._subtitle_editor_controller

    @property
    def translation_controller(self) -> TranslationController:
        """获取翻译控制器实例。

        Returns:
            TranslationController: 翻译控制器实例。
        """
        return self._translation_controller

    @property
    def translation_service(self) -> TranslationService:
        """获取翻译服务实例。

        Returns:
            TranslationService: 翻译服务实例。
        """
        return self._translation_service

    def run(self) -> None:
        """构建并启动 Gradio UI 应用程序。"""
        ui = create_ui(self)
        ui.launch()


# 应用程序状态与实例别名，保持与测试架构的兼容性
AppState = Application
