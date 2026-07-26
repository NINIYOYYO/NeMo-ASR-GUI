import logging
import re
from pathlib import Path

import yaml


class ConfigurableFilter(logging.Filter):
    """
    一个可配置的日志过滤器，允许基于正则表达式和日志级别过滤日志消息。
    """

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__()
        self.message_patterns: list = []

        if config_path:
            self._load_config(config_path)

    def _load_config(self, config_path: str):
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

                #编译正则表达式模式
                filters = config.get('message_filters', [])
                for filter_rule in filters:
                    pattern = re.compile(filter_rule.get('pattern', ''))
                    min_level = getattr(logging, filter_rule.get('level', 'DEBUG'))
                    self.message_patterns.append(
                        {
                            'pattern': pattern,
                            'level': min_level
                        }
                    )
        except Exception as e:
            logging.warning(f"无法加载日志过滤配置: {e}")

    def filter(self, record):
        """过滤日志记录"""

        message = record.getMessage()

        #检查消息是否匹配任何过滤模式
        for rule in self.message_patterns:
            if rule['pattern'].search(message):
                # 如果记录级别低于规则的最小级别，则过滤掉
                if record.levelno < rule['min_level']:
                    return False
        return True
    

def apply_third_party_filters(config_path: str | None = None):
    """
    应用第三方库的日志过滤器。
    """
    path = Path(config_path) if config_path else Path(__file__).parent.parent / "logging_filter_config.yaml"

    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        for logger_config in config.get('third_party_loggers', []):
            logger_name = logger_config.get('name', '')
            level = getattr(logging, logger_config['level'])
            logging.getLogger(logger_name).setLevel(level)
            
    except Exception as e:
        logging.warning(f"无法应用第三方日志过滤配置: {e}")


