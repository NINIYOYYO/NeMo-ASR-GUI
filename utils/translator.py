"""国际化多语言翻译器模块。

提供单例模式的 UI 文本与错误提示多语言加载、切换及动态参数插值格式化。
"""

import json
from pathlib import Path
from typing import Any, ClassVar

from core.constants import DEFAULT_LANGUAGE
from utils.logger import logger

BASE_DIR: Path = Path(__file__).resolve().parent.parent
LOCALE_DIR: Path = BASE_DIR / "locales"


class Translator:
    """国际化翻译器单例类。"""

    _instance: ClassVar["Translator | None"] = None
    _current_locale: ClassVar[str] = DEFAULT_LANGUAGE
    _initialized: bool = False

    def __new__(cls, locale: str | None = None) -> "Translator":
        """实现单例模式，确保只有一个翻译器实例。

        Args:
            locale (str | None): 初始语言标识。

        Returns:
            Translator: 唯一的翻译器实例。
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False

        return cls._instance

    def __init__(self, locale: str = DEFAULT_LANGUAGE) -> None:
        """初始化翻译器。

        Args:
            locale (str): 语言标识（如 'zh', 'en', 'ja', 'ko'）。
        """
        if self._initialized:
            if locale and locale != self._current_locale:
                self.set_locale(locale)
            return

        self.locale: str = locale or self._current_locale
        self.translations: dict[str, Any] = self._load_translations()
        self._initialized = True

    def _load_translations(self) -> dict[str, Any]:
        """加载指定语言的翻译文件。

        Returns:
            dict[str, Any]: 加载解析后的翻译键值字典。
        """
        file_path = LOCALE_DIR / f"{self.locale}.json"

        if not file_path.exists():
            logger.warning(f"未找到翻译文件 {file_path}")
            return {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载翻译文件时出错: {e}")
            return {}

    def set_locale(self, locale: str) -> None:
        """切换当前激活的界面语言。

        Args:
            locale (str): 新的目标语言代码。
        """
        if locale != self.locale:
            self.locale = locale
            self.__class__._current_locale = locale
            self.translations = self._load_translations()
            logger.info(f"语言已切换为: {locale}")

    def get_current_locale(self) -> str:
        """获取当前激活的语言代码。

        Returns:
            str: 当前语言代码。
        """
        return self.locale

    def __call__(self, key: str, **kwargs: Any) -> str:
        """获取并格式化翻译文本。

        Args:
            key (str): 翻译键，支持点号分隔的嵌套键，如 "model.load_success_cloud"。
            **kwargs: 动态字符串插值参数。

        Returns:
            str: 翻译并插值完成的文本。
        """
        keys = key.split(".")
        translation: Any = self.translations

        for k in keys:
            if isinstance(translation, dict) and k in translation:
                translation = translation.get(k)
            else:
                translation = None
                break

        # 如果未找到翻译，返回键本身
        if translation is None:
            logger.warning(f"未找到翻译键: {key}")
            return key

        try:
            return str(translation).format(**kwargs) if kwargs else str(translation)
        except KeyError as e:
            logger.error(f"翻译格式化错误: 缺少参数 {e} for key {key}")
            return str(translation)


t: Translator = Translator()


def set_language(locale: str) -> None:
    """设置当前全局语言。

    Args:
        locale (str): 目标语言代码。
    """
    t.set_locale(locale)


def get_language() -> str:
    """获取当前全局语言代码。

    Returns:
        str: 当前语言代码。
    """
    return t.get_current_locale()