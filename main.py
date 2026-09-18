import builtins
import os
import sys

# 强制开启 Python UTF-8 运行环境
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

# Windows 平台标准输出与默认文件 I/O 编码保护，防止第三方库 (如 PyTorch / NeMo) 在 GBK 环境下崩溃
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    _original_open = builtins.open

    def _safe_utf8_open(*args, **kwargs):  # type: ignore[no-untyped-def]
        """在 Windows 平台下为文本模式 open() 注入默认 UTF-8 编码。

        Args:
            *args: 位置参数。
            **kwargs: 关键字参数。

        Returns:
            IO 句柄实例。
        """
        mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
        if "b" not in str(mode) and "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
        return _original_open(*args, **kwargs)

    builtins.open = _safe_utf8_open

from application import Application
from core.asr_service import ASRService
from core.audio_processor import AudioService
from core.subtitle_generator import SubtitleService
from utils.config_manager import ConfigManager
from utils.logger import logger


def create_app() -> Application:
    """创建并返回应用程序实例。

    Returns:
        Application: 配置好所有服务与控制器的核心应用实例。
    """
    config = ConfigManager()
    asr_service = ASRService()
    audio_service = AudioService()
    subtitle_generator = SubtitleService()

    return Application(
        config_manager=config,
        asr_service=asr_service,
        audio_service=audio_service,
        subtitle_generator=subtitle_generator,
    )


if __name__ == "__main__":
    logger.info("启动 ASR 应用程序...")
    app = create_app()
    app.run()
    logger.info("ASR 应用程序已关闭。")





