import atexit
import logging
import logging.handlers
import os
import queue
import sys
from pathlib import Path

from utils.log_filter import ConfigurableFilter, apply_third_party_filters

_listener = None
_is_initialized = False
BASE_DIR = Path(__file__).parent.parent
LOG_DIR = BASE_DIR / "logs"
if not LOG_DIR.exists():
    LOG_DIR.mkdir(parents=True)



class SafeStreamHandler(logging.StreamHandler):
    """防止在解释器退出阶段向已关闭的 stream 输出时产生未捕获异常。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self.stream and not getattr(self.stream, "closed", False):
                super().emit(record)
        except Exception:
            self.handleError(record)


def _create_default_filter():
    """创建默认过滤器（当没有配置文件时）。
    注意：必须定义在 _initialize_logging_system 调用它之前，
    否则 yaml 配置文件缺失时会因函数未定义而导致启动崩溃。
    """
    class DefaultFilter(logging.Filter):
        THIRD_PARTY = ('torio', 'matplotlib', 'graphviz', 'torch')

        def filter(self, record):
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


def _initialize_logging_system():
    """
    一个内部函数，只在第一次导入时执行一次。
    它负责创建和启动整个非阻塞日志系统。
    """
    global _listener, _is_initialized
    if _is_initialized:
        return
    
    # 1. 创建一个队列，这是生产者和消费者之间的“邮箱”
    log_queue: queue.Queue = queue.Queue(-1)  # 无限大小的队列

    # 2. 创建一个处理器，将日志消息发送到队列
    # 这些 handlers 将由后台的 listener 线程使用，来执行慢速的 I/O 操作
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "app.log"), maxBytes=5*1024*1024, backupCount=5, encoding="utf-8"
    )
    file_formatter = logging.Formatter(
        '%(asctime)s - %(filename)-18s:%(lineno)4d - %(levelname)s - %(message)s'
    )

    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)  # 文件处理器记录所有级别的日志

    console_handler = SafeStreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(filename)-18s:%(lineno)4d -  %(levelname)s - %(message)s', datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)  # 控制台处理器只记录 INFO 及以上级别的日志

    # 应用第三方库的日志过滤器
    config_path = Path(__file__).parent.parent / "logging_filter_config.yaml"
    if config_path.exists():
        console_handler.addFilter(ConfigurableFilter(str(config_path)))
    else:
        # 如果没有配置文件，应用默认过滤器
        console_handler.addFilter(_create_default_filter())


    # 3. 创建一个 QueueHandler(消费者/后台线程)，将日志消息放入队列
    # 它监听 log_queue，并将日志分发给 file_handler 和 console_handler
    _listener = logging.handlers.QueueListener(log_queue, file_handler, console_handler, respect_handler_level=True)
    _listener.start()



    # 4. 配置根记录器使用 QueueHandler(生产者)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 设置根记录器的日志级别

    #移除所有现有处理器，防止重复日志
    root_logger.handlers = []

    # 添加 QueueHandler，它是唯一连接到 logger 的 handler
    queue_handler = logging.handlers.QueueHandler(log_queue)
    root_logger.addHandler(queue_handler)

    # 应用第三方库的日志过滤器
    if config_path.exists():
        apply_third_party_filters(str(config_path))

           


    #5. 标记为已初始化，并注册退出函数
    _is_initialized = True
    atexit.register(stop_logging)# 注册 stop_logging，以便程序退出时自动调用

    root_logger.info("日志系统已初始化。")


_initialize_logging_system()


logger = logging.getLogger("ASR_App")

logger.setLevel(logging.INFO)

def get_logger(name: str):
    """ 获取一个以指定名称命名的 logger。
    由于根 logger 已经配置好，这个 logger 会自动将日志发送到我们的非阻塞系统中。
    """
    return logging.getLogger(name)

