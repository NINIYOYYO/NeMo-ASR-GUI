from application import Application
from core.asr_service import ASRService
from core.audio_processor import AudioService
from core.subtitle_generator import SubtitleService
from utils.config_manager import ConfigManager
from utils.logger import logger


def create_app() -> Application:
    """创建并返回应用程序实例。"""
    config = ConfigManager()
    asr_service = ASRService()
    audio_service = AudioService()
    subtitle_generator = SubtitleService()
    
    return Application(
        config_manager=config,
        asr_service=asr_service,
        audio_service=audio_service,
        subtitle_generator=subtitle_generator
    )


if __name__ == "__main__":

    logger.info("启动 ASR 应用程序...")
    app = create_app()
    app.run()
    logger.info("ASR 应用程序已关闭。")




