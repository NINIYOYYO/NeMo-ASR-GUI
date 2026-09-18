"""应用程序配置管理模块。

负责读写 config.json 配置文件，并提供线程安全的默认配置降级保障。
"""

import json
import os
from typing import Any

from core.constants import (
    DEFAULT_CHUNK_LENGTH_S,
    DEFAULT_CLOUD_MODEL,
    DEFAULT_CONFIG_FILENAME,
    DEFAULT_LANGUAGE,
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
)
from interfaces import IConfigManager
from utils.logger import logger


class ConfigManager(IConfigManager):
    """负责所有与 config.json 文件的读取和写入操作。"""

    CONFIG_FILENAME: str = DEFAULT_CONFIG_FILENAME
    DEFAULT_CONFIG: dict[str, Any] = {
        "local_model_path": None,
        "chunk_length_s": DEFAULT_CHUNK_LENGTH_S,
        "cloud_model_name": DEFAULT_CLOUD_MODEL,
        "language": DEFAULT_LANGUAGE,
        "api_key": "",
        "base_url": DEFAULT_LLM_BASE_URL,
        "llm_model": DEFAULT_LLM_MODEL,
        "proxy": "",
    }

    def __init__(self, base_dir: str | None = None) -> None:
        """初始化配置管理器。

        Args:
            base_dir (str | None): 配置文件所在根目录路径，为 None 时使用项目根目录。
        """
        if not base_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.config_path: str = os.path.join(base_dir, self.CONFIG_FILENAME)
        self.config: dict[str, Any] = self._load_config()
        logger.info(f"配置管理器已初始化。配置文件路径: {self.config_path}")

    def _load_config(self) -> dict[str, Any]:
        """从 config.json 加载配置。

        Returns:
            dict[str, Any]: 加载并补全默认值的配置字典。
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as config_file:
                    loaded_config: dict[str, Any] = json.load(config_file)
                    # 确保基本键存在，如果不存在则提供默认值
                    for key, value in self.DEFAULT_CONFIG.items():
                        loaded_config.setdefault(key, value)

                    return loaded_config

            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"错误: 配置文件 {self.config_path} :{e}格式错误。使用默认配置。")
                return self.DEFAULT_CONFIG.copy()
        else:
            logger.info(f"配置文件 {self.config_path} 未找到。将使用默认设置 (首次运行)。")
            return self.DEFAULT_CONFIG.copy()

    def get_config_value(self, key: str) -> Any:
        """获取配置中的特定值。

        Args:
            key (str): 配置项键名。

        Returns:
            Any: 配置项的值，若不存在则返回默认值。
        """
        return self.config.get(key, self.DEFAULT_CONFIG.get(key))

    def get_config_all(self) -> dict[str, Any]:
        """获取整个配置字典。

        Returns:
            dict[str, Any]: 当前配置字典副本。
        """
        return self.config.copy()

    def save_config(self, **kwargs: Any) -> None:
        """保存配置到 config.json 文件。

        Args:
            **kwargs: 键值对配置项（例如 local_model_path, chunk_length_s, cloud_model_name, language 等）。
        """
        # 1. 拿出现有的配置作为基础
        current_config = self.get_config_all()

        # 2. 用传入的新值覆盖旧值
        for key, value in kwargs.items():
            if key in current_config:
                current_config[key] = value
            else:
                logger.warning(
                    f"save_config 收到未知配置键 '{key}'，已忽略。有效键: {list(self.DEFAULT_CONFIG.keys())}"
                )

        try:
            with open(self.config_path, "w", encoding="utf-8") as config_file:
                json.dump(current_config, config_file, indent=4)
            self.config = current_config  # 更新内存中的配置
            logger.info(f"配置已保存到 {self.config_path}")
        except Exception as e:
            logger.error(f"错误：保存配置文件 '{self.config_path}' 失败: {e}")
