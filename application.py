from interfaces import (
    IApplication,
    IAudioService,
    IConfigManager,
    ISubtitleGenerator,
    IASRService,
    IModelController,
    ITranscriptionController,
    
    
)

# 导入控制器类
from controllers.model_controller import ModelController
from controllers.transcription_controller import TranscriptionController
from controllers.subtitle_editor_controller import SubtitleEditorController
from core.translation_service import TranslationService
from controllers.translation_controller import TranslationController

from app_ui import create_ui
from utils.logger import logger


class Application(IApplication):
    """
    封装应用的所有状态和核心服务，并协调各个控制器。
    """

    def __init__(
        self,
        config_manager: IConfigManager,
        asr_service: IASRService,
        audio_service: IAudioService,
        subtitle_generator: ISubtitleGenerator,
    ) -> None:

        # 初始化核心服务
        self._config_manager = config_manager
        self._asr_service = asr_service
        self._audio_service = audio_service
        self._subtitle_service = subtitle_generator

        # 初始化控制器
        self._model_controller = ModelController(
            app_services=self._asr_service, config=self._config_manager
        )
        self._transcription_controller = TranscriptionController(
            app_services=self.asr_service,
            audio_service=self.audio_service,
            subtitle_generator=self._subtitle_service,
        )

        self._subtitle_editor_controller = SubtitleEditorController(
            subtitle_service=self._subtitle_service
        )

        self._translation_service = TranslationService()
        self._translation_controller = TranslationController(
            subtitle_service=self._subtitle_service,
            translation_service=self._translation_service,
            config_manager=self._config_manager
        )

    @property
    def asr_service(self) -> IASRService:
        """获取 ASR 服务实例。"""
        return self._asr_service

    @property
    def config_manager(self) -> IConfigManager:
        """获取配置管理器实例。"""
        return self._config_manager

    @property
    def audio_service(self) -> IAudioService:
        """获取音频处理服务实例。"""
        return self._audio_service

    @property
    def subtitle_generator(self) -> ISubtitleGenerator:
        """获取字幕生成服务实例。"""
        return self._subtitle_service

    @property
    def model_controller(self) -> ModelController:
        """获取模型控制器实例。"""
        return self._model_controller

    @property
    def transcription_controller(self) -> TranscriptionController:
        """获取转录控制器实例。"""
        return self._transcription_controller
    
    @property
    def subtitle_editor_controller(self) -> SubtitleEditorController:
        return self._subtitle_editor_controller
    
    @property
    def translation_controller(self) -> TranslationController:
        return self._translation_controller
    
    @property
    def translation_service(self) -> TranslationService:
        return self._translation_service

    def run(self):
        """启动 Gradio UI 应用程序。"""
        ui = create_ui(self)
        ui.launch()
