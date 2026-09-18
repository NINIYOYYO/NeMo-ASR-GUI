"""系统自定义异常定义模块。

定义应用体系中各类业务与运行时异常基类与子类。
"""


class BaseAppException(Exception):
    """应用程序所有自定义异常的基类。"""

    pass


class ModelLoadError(BaseAppException):
    """模型加载失败时引发的异常。"""

    pass


class AudioProcessingError(BaseAppException):
    """当音频提取或转换失败时引发。"""

    pass


class TranscriptionError(BaseAppException):
    """当转录过程失败时引发。"""

    pass


class SubtitleGenerationError(BaseAppException):
    """当 SRT 内容生成失败时引发。"""

    pass
