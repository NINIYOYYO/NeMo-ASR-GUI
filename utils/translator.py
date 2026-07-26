import json
from pathlib import Path

from utils.logger import logger

BASE_DIR = Path(__file__).resolve().parent.parent

LOCALE_DIR = BASE_DIR / "locales"


class Translator:
    """国际化翻译器"""

    _instance = None
    _current_locale = "zh"  # 默认语言
    _initialized: bool = False

    def __new__(cls, locale=None):
        """实现单例模式，确保只有一个翻译器实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False

        return cls._instance
        

    def __init__(self, locale="zh") -> None:

        if self._initialized:
            if locale and locale != self._current_locale:
                self.set_locale(locale)
            return

        self.locale = locale or self._current_locale
        self.translations = self._load_translations()
        self._initialized = True

    def _load_translations(self):
        """加载指定语言的翻译文件"""

        file_path = LOCALE_DIR / f"{self.locale}.json"

        if not file_path.exists():
            logger.warning(f"未找到翻译文件{file_path}")
            return {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"加载翻译文件时出错: {e}")
            return {}

    def set_locale(self, locale: str):
        """切换语言"""
        if locale != self.locale:
            self.locale = locale
            self.__class__._current_locale = locale
            self.translations = self._load_translations()
            logger.info(f"语言已切换为: {locale}")

    def get_current_locale(self) -> str:
        """获取当前语言"""
        return self.locale

    def __call__(self, key: str, **kwargs):
        """
        获取翻译文本
        
        Args:
            key: 翻译键，支持点号分隔的嵌套键，如 "model.load_success_cloud"
            **kwargs: 格式化参数
            
        Returns:
            翻译后的文本
        """

        keys = key.split(".")
        translation = self.translations

        for k in keys:
            if isinstance(translation, dict) and k in translation:
                translation = translation.get(k)
            else:
                translation = None
                break
        
        #如果未找到翻译，返回键本身
        if translation is None:
            logger.warning(f"未找到翻译键: {key}")
            return key
        
        try:

            return translation.format(**kwargs) if kwargs else translation
        except KeyError as e:
            logger.error(f"翻译格式化错误: 缺少参数 {e} for key {key}")
            return translation

t = Translator()


def set_language(locale: str):
    """设置当前语言"""
    t.set_locale(locale)

def get_language() -> str:
    """获取当前语言"""
    return t.get_current_locale()