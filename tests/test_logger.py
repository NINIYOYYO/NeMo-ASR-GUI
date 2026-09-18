"""针对日志系统与日志过滤器的单元测试。"""

import logging
from pathlib import Path

from utils.log_filter import ConfigurableFilter, apply_third_party_filters
from utils.logger import SafeStreamHandler, get_logger


def test_configurable_filter_min_level_match(tmp_path: Path) -> None:
    """测试日志过滤器能够正确匹配正则并在低于 min_level 时予以过滤（无 KeyError: min_level）。"""
    config_file = tmp_path / "filter_test.yaml"
    config_content = """
message_filters:
  - pattern: "Ignored debug noise"
    level: "WARNING"
"""
    config_file.write_text(config_content, encoding="utf-8")

    flt = ConfigurableFilter(str(config_file))
    assert len(flt.message_patterns) == 1
    assert flt.message_patterns[0]["min_level"] == logging.WARNING

    # 1. 匹配正则但级别为 DEBUG (低于 WARNING) -> 拦截 (False)
    rec_debug = logging.LogRecord(
        name="test_logger",
        level=logging.DEBUG,
        pathname=__file__,
        lineno=1,
        msg="Ignored debug noise occurred",
        args=(),
        exc_info=None,
    )
    assert flt.filter(rec_debug) is False

    # 2. 匹配正则且级别为 WARNING (等于 WARNING) -> 放行 (True)
    rec_warn = logging.LogRecord(
        name="test_logger",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Ignored debug noise critical warning",
        args=(),
        exc_info=None,
    )
    assert flt.filter(rec_warn) is True

    # 3. 不匹配正则 -> 放行 (True)
    rec_normal = logging.LogRecord(
        name="test_logger",
        level=logging.DEBUG,
        pathname=__file__,
        lineno=1,
        msg="Normal message without match",
        args=(),
        exc_info=None,
    )
    assert flt.filter(rec_normal) is True


def test_safe_stream_handler_closed_stream() -> None:
    """测试 SafeStreamHandler 在目标流已关闭时不会抛出未捕获异常。"""

    class MockClosedStream:
        closed = True

        def write(self, data: str) -> None:
            raise ValueError("I/O operation on closed file")

        def flush(self) -> None:
            raise ValueError("I/O operation on closed file")

    handler = SafeStreamHandler(MockClosedStream())
    rec = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Test message during shutdown",
        args=(),
        exc_info=None,
    )
    # 应安全静默返回，不抛出 ValueError
    handler.emit(rec)


def test_apply_third_party_filters(tmp_path: Path) -> None:
    """测试第三方日志过滤器配置生效。"""
    config_file = tmp_path / "third_party.yaml"
    config_content = """
third_party_loggers:
  - name: "test_pkg_dummy"
    level: "ERROR"
"""
    config_file.write_text(config_content, encoding="utf-8")
    apply_third_party_filters(str(config_file))
    pkg_logger = logging.getLogger("test_pkg_dummy")
    assert pkg_logger.level == logging.ERROR


def test_get_logger() -> None:
    """测试 get_logger 辅助函数返回正确的 Logger 实例。"""
    lg = get_logger("my_custom_module")
    assert lg.name == "my_custom_module"
