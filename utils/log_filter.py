"""可配置日志过滤器模块。

提供基于 YAML 配置文件、正则表达式与日志等级阈值的消息级与模块级过滤。
"""

import logging
import re
from pathlib import Path
from typing import Any

import yaml


class ConfigurableFilter(logging.Filter):
    """基于正则表达式和日志级别过滤日志消息的可配置过滤器。"""

    def __init__(self, config_path: str | None = None) -> None:
        """初始化日志过滤器并可选择性加载外部 YAML 配置文件。

        Args:
            config_path (str | None): 日志过滤 YAML 配置文件路径，为 None 时不预先加载。
        """
        super().__init__()
        self.message_patterns: list[dict[str, Any]] = []

        if config_path:
            self._load_config(config_path)

    def _load_config(self, config_path: str) -> None:
        """从指定路径加载 YAML 日志过滤配置。

        Args:
            config_path (str): 配置文件绝对或相对路径。
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            config: dict[str, Any] = {}
            try:
                config = yaml.safe_load(content) or {}
            except yaml.YAMLError:
                # 针对双引号内含有未转义正则表达式（如 \.、\d、\[ 等）的容错处理
                sanitized = re.sub(
                    r'pattern:\s*"([^"]*)"',
                    lambda m: "pattern: '" + m.group(1).replace("'", "''") + "'",
                    content,
                )
                try:
                    config = yaml.safe_load(sanitized) or {}
                except Exception:
                    config = {}

            # 编译正则表达式模式并存储 min_level 规则
            filters = config.get("message_filters", []) if isinstance(config, dict) else []
            for filter_rule in filters:
                if not isinstance(filter_rule, dict):
                    continue
                pattern_str = filter_rule.get("pattern", "")
                if not pattern_str:
                    continue
                pattern = re.compile(pattern_str)
                level_name = str(
                    filter_rule.get("min_level") or filter_rule.get("level", "DEBUG")
                )
                min_level = getattr(logging, level_name.upper(), logging.DEBUG)
                self.message_patterns.append(
                    {
                        "pattern": pattern,
                        "min_level": min_level,
                        "level": min_level,
                    }
                )
        except Exception as e:
            logging.warning(f"无法加载日志过滤配置: {e}")

    def filter(self, record: logging.LogRecord) -> bool:
        """根据配置的正则模式和级别判定是否放行当前日志记录。

        Args:
            record (logging.LogRecord): 待判定的日志记录实体。

        Returns:
            bool: True 表示放行该日志，False 表示拦截并丢弃该日志。
        """
        message = record.getMessage()

        # 检查消息是否匹配任何过滤模式
        for rule in self.message_patterns:
            if rule["pattern"].search(message):
                # 如果记录级别低于规则的最小级别，则过滤掉
                if record.levelno < rule["min_level"]:
                    return False
        return True


def apply_third_party_filters(config_path: str | None = None) -> None:
    """读取配置文件并对指定的第三方库日志记录器设置最低过滤级别。

    Args:
        config_path (str | None): 日志过滤 YAML 配置文件路径，为 None 时使用默认路径。
    """
    path = (
        Path(config_path)
        if config_path
        else Path(__file__).parent.parent / "logging_filter_config.yaml"
    )

    try:
        with open(path, "r", encoding="utf-8") as f:
            config: dict[str, Any] = yaml.safe_load(f) or {}

        for logger_config in config.get("third_party_loggers", []):
            logger_name = logger_config.get("name", "")
            if logger_name:
                level = getattr(
                    logging,
                    str(logger_config.get("level", "WARNING")).upper(),
                    logging.WARNING,
                )
                logging.getLogger(logger_name).setLevel(level)

    except Exception as e:
        logging.warning(f"无法应用第三方日志过滤配置: {e}")
