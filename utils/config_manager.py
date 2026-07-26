import json
import os

from interfaces import IConfigManager
from utils.logger import logger


class ConfigManager(IConfigManager):
    """负责所有与 config.json 文件的读取和写入操作。"""
    
    CONFIG_FILENAME = "config.json"
    DEFAULT_CONFIG = {
        "local_model_path": None,
        "chunk_length_s": 60,
        "cloud_model_name": "nvidia/parakeet-tdt-0.6b-v2",
        "language": "zh",
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "llm_model": "gpt-5.2",
        "proxy": ""
    }
    
    def __init__(self, base_dir=None) -> None:
        if not base_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.config_path = os.path.join(base_dir, self.CONFIG_FILENAME)
        self.config = self._load_config()
        logger.info(f"配置管理器已初始化。配置文件路径: {self.config_path}")



    def _load_config(self) -> dict:
        """从 config.json 加载配置。
        返回一个包含 'local_model_path' (可以为 None)、'chunk_length_s' 和 'cloud_model_name' 的字典。
        """

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as config_file:
                    loaded_config = json.load(config_file)
                    # 确保基本键存在，如果不存在则提供默认值

                    for key, value in self.DEFAULT_CONFIG.items():
                        loaded_config.setdefault(key, value)

                    return loaded_config

            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"错误: 配置文件 {self.config_path} :{e}格式错误。使用默认配置。")
                
                return self.DEFAULT_CONFIG.copy()
            
        else:
            logger.info(f"配置文件 {self.config_path} 未找到。将使用默认设置 (首次运行)。")
            return self.DEFAULT_CONFIG.copy()


    def get_config_value(self, key: str):
        """获取配置中的特定值。"""

        return self.config.get(key, self.DEFAULT_CONFIG.get(key))
    
    def get_config_all(self) -> dict:
        """获取整个配置字典。"""
        return self.config.copy()


    def save_config(self,**kwargs) -> None:
        """
        保存配置到 config.json 文件。
        :param kwargs: 接受以下关键字参数:
        - local_model_path (str): 本地模型路径
        - chunk_length_s (int): 分块长度（秒）
        - cloud_model_name (str): 云端模型名称
        - language (str): 界面语言
        """

        # 1. 拿出现有的配置作为基础
        current_config = self.get_config_all()

         # 2. 用传入的新值覆盖旧值 (如果 kwargs 里没传某个键，旧值会被保留)
        for key, value in kwargs.items():
            if key in current_config:
                current_config[key] = value
            else:
                # 未知键名不再静默丢弃，打警告方便及时发现调用方的键名拼写错误
                logger.warning(f"save_config 收到未知配置键 '{key}'，已忽略。有效键: {list(self.DEFAULT_CONFIG.keys())}")

        try:
            with open(self.config_path, "w", encoding="utf-8") as config_file:
                json.dump(current_config, config_file, indent=4)
            self.config = current_config  #更新内存中的配置
            logger.info(f"配置已保存到 {self.config_path}")
        except Exception as e:
            logger.error(f"错误：保存配置文件 '{self.config_path}' 失败: {e}")


   