"""全局日志记录与异步 QueueListener 日志系统。

采用生产者-消费者模型实现非阻塞日志记录，并支持日志按体积轮转和基于正则的级别过滤。
"""

import atexit
import logging
import logging.handlers
import os
import queue
import sys
from pathlib import Path

from core.constants import (
    DEFAULT_LOG_BACKUP_COUNT,
    DEFAULT_LOG_FILENAME,
    DEFAULT_LOG_MAX_BYTES,
)
from utils.log_filter import ConfigurableFilter, apply_third_party_filters

_listener: logging.handlers.QueueListener | None = None
_is_initialized: bool = False
BASE_DIR: Path = Path(__file__).parent.parent
LOG_DIR: Path = BASE_DIR / "logs"
if not LOG_DIR.exists():
    LOG_DIR.mkdir(parents=True)


class SafeStreamHandler(logging.StreamHandler):
    """防止在解释器退出阶段向已关闭的 stream 输出时产生未捕获异常。"""

    def emit(self, record: logging.LogRecord) -> None:
        """向输出流安全写入日志记录。

        Args:
            record (logging.LogRecord): 待输出的日志记录。
        """
        try:
            if self.stream and not getattr(self.stream, "closed", False):
                super().emit(record)
        except Exception:
            self.handleError(record)


def _create_default_filter() -> logging.Filter:
    """创建默认过滤器（当没有配置文件时）。

    Returns:
        logging.Filter: 针对第三方库的日志过滤器。
    """

    class DefaultFilter(logging.Filter):
        """过滤第三方库嘈杂日志的默认过滤器。"""

        THIRD_PARTY = ("torio", "matplotlib", "graphviz", "torch")

        def filter(self, record: logging.LogRecord) -> bool:
            """判断是否放行日志记录。

            Args:
                record (logging.LogRecord): 待判定的日志记录实体。

            Returns:
                bool: 如果放行则返回 True，否则返回 False。
            """
            # 只过滤第三方库的 DEBUG 日志
            if record.name.startswith(self.THIRD_PARTY):
                return record.levelno >= logging.WARNING
            return True

    return DefaultFilter()


def stop_logging() -> None:
    """停止日志监听器并清理资源。"""
    global _listener
    if _listener:
        try:
            logging.info("应用程序正在关闭，停止日志系统...")
        except Exception:
            pass
        try:
            _listener.stop()
        except Exception:
            pass
        try:
            if sys.stdout and not getattr(sys.stdout, "closed", False):
                print("日志系统已成功停止。")
        except Exception:
            pass
        _listener = None


def _initialize_logging_system() -> None:
    """内部函数，只在第一次导入时执行一次。

    负责创建和启动整个非阻塞日志系统。
    """
    global _listener, _is_initialized
    if _is_initialized:
        return

    # 1. 创建无限大小队列作为生产者和消费者之间的邮箱
    log_queue: queue.Queue = queue.Queue(-1)

    # 2. 创建日志处理器并配置格式化器
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, DEFAULT_LOG_FILENAME),
        maxBytes=DEFAULT_LOG_MAX_BYTES,
        backupCount=DEFAULT_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_formatter = logging.Formatter(
        "%(asctime)s - %(filename)-18s:%(lineno)4d - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = SafeStreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(filename)-18s:%(lineno)4d -  %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)

    # 应用第三方库日志过滤器
    config_path = Path(__file__).parent.parent / "logging_filter_config.yaml"
    if config_path.exists():
        console_handler.addFilter(ConfigurableFilter(str(config_path)))
    else:
        console_handler.addFilter(_create_default_filter())

    # 3. 创建 QueueListener 消费后台日志
    _listener = logging.handlers.QueueListener(
        log_queue, file_handler, console_handler, respect_handler_level=True
    )
    _listener.start()

    # 4. 配置根记录器使用 QueueHandler
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers = []

    queue_handler = logging.handlers.QueueHandler(log_queue)
    root_logger.addHandler(queue_handler)

    if config_path.exists():
        apply_third_party_filters(str(config_path))

    # 5. 注册退出清理钩子
    _is_initialized = True
    atexit.register(stop_logging)

    root_logger.info("日志系统已初始化。")


_initialize_logging_system()

logger = logging.getLogger("ASR_App")
logger.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """获取一个以指定名称命名的 logger。

    Args:
        name (str): 记录器名称。

    Returns:
        logging.Logger: 配置好异步处理的日志记录器实例。
    """
    return logging.getLogger(name)
