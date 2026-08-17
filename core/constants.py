"""系统全局常量定义与枚举模块。

集中管理音频处理、模型推理、时间转换、LLM 翻译、日志配置与 UI 参数等魔法数字与常量。
"""

from enum import Enum
from typing import Final

# ==============================================================================
# 音频处理与预处理常量
# ==============================================================================
DEFAULT_SAMPLE_RATE: Final[int] = 16000
DEFAULT_AUDIO_CHANNELS: Final[int] = 1
AUDIO_NORM_FACTOR: Final[float] = 32768.0  # 16-bit PCM 归一化分母

DEFAULT_CHUNK_DURATION_SEC: Final[float] = 30.0
DEFAULT_CHUNK_LENGTH_S: Final[int] = 60
DEFAULT_CHUNK_LENGTH_MS: Final[int] = 60000
DEFAULT_SLIDE_OVERLAP_SEC: Final[float] = 1.0

# 字幕段落与时间轴保护常量 (秒)
MIN_SEGMENT_DURATION_SEC: Final[float] = 0.05
SEGMENT_BOUNDARY_GUARD_SEC: Final[float] = 0.01
SEGMENT_TOLERANCE_OFFSET_SEC: Final[float] = 0.05
SPLIT_TOLERANCE_OFFSET_SEC: Final[float] = 0.02

# 日语字符级重组策略常量
DEFAULT_MAX_DURATION_SEC: Final[float] = 8.0
DEFAULT_MAX_CHARS: Final[int] = 40
DEFAULT_SOFT_LIMIT_CHARS: Final[int] = 20
SILENCE_THRESHOLD_SEC: Final[float] = 0.45
MIN_JAPANESE_SEGMENT_DURATION_SEC: Final[float] = 0.5

# ==============================================================================
# 时间与时间戳转换常量
# ==============================================================================
MS_PER_SECOND: Final[int] = 1000
SECONDS_PER_MINUTE: Final[int] = 60
SECONDS_PER_HOUR: Final[int] = 3600
MS_PER_MINUTE: Final[int] = 60_000
MS_PER_HOUR: Final[int] = 3600_000
CENTISECONDS_PER_SECOND: Final[int] = 100

# ==============================================================================
# 大语言模型 (LLM) 与翻译服务常量
# ==============================================================================
DEFAULT_LLM_TIMEOUT_SEC: Final[float] = 180.0
DEFAULT_LLM_TEMPERATURE: Final[float] = 0.1
DEFAULT_MAX_RETRIES: Final[int] = 3
DEFAULT_RATE_LIMIT_WAIT_SEC: Final[float] = 20.0

DEFAULT_TRANSLATION_CONCURRENCY: Final[int] = 5
DEFAULT_TRANSLATION_CHUNK_SIZE: Final[int] = 30
DEFAULT_SEGMENTATION_CONCURRENCY: Final[int] = 3
DEFAULT_SEGMENTATION_CHUNK_SIZE: Final[int] = 50

DEFAULT_LLM_BASE_URL: Final[str] = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL: Final[str] = "gpt-5.2"

# ==============================================================================
# 模型与语言默认值
# ==============================================================================
DEFAULT_CLOUD_MODEL: Final[str] = "nvidia/parakeet-tdt-0.6b-v2"
DEFAULT_LANGUAGE: Final[str] = "zh"

AVAILABLE_MODELS: Final[dict[str, str]] = {
    "nvidia/parakeet-tdt-0.6b-v2": "只支持英语",
    "nvidia/parakeet-tdt_ctc-110m": "轻量级英语",
    "nvidia/parakeet-tdt-0.6b-v3": (
        "支持保加利亚语 (bg)、克罗地亚语 (hr)、捷克语 (cs)、丹麦语 (da)、荷兰语 (nl)、"
        "英语 (en)、爱沙尼亚语 (et)、芬兰语 (fi)、法语 (fr)、德语 (de)、希腊语 (el)、"
        "匈牙利语 (hu)、意大利语 (it)、拉脱维亚语 (lv)、立陶宛语 (lt)、马耳他语 (mt)、"
        "波兰语 (pl)、葡萄牙语 (pt)、罗马尼亚语 (ro)、斯洛伐克语 (sk)、斯洛文语 (sl)、"
        "西班牙语 (es)、瑞典语 (sv)、俄语 (ru)、乌克兰语 (uk)"
    ),
    "nvidia/parakeet-tdt_ctc-0.6b-ja": "日语模型，支持日语转录",
}

# ==============================================================================
# 日志与持久化存储常量
# ==============================================================================
DEFAULT_LOG_MAX_BYTES: Final[int] = 5 * 1024 * 1024  # 5 MB
DEFAULT_LOG_BACKUP_COUNT: Final[int] = 5
DEFAULT_LOG_FILENAME: Final[str] = "app.log"
DEFAULT_CONFIG_FILENAME: Final[str] = "config.json"
DEFAULT_CORRECTIONS_FILENAME: Final[str] = "corrections.json"

# ==============================================================================
# UI 控件范围常量
# ==============================================================================
CHUNK_SLIDER_MIN: Final[int] = 10
CHUNK_SLIDER_MAX: Final[int] = 300
CHUNK_SLIDER_STEP: Final[int] = 5

MAX_LINE_WIDTH_MIN: Final[int] = 10
MAX_LINE_WIDTH_MAX: Final[int] = 100
MAX_LINE_WIDTH_DEFAULT: Final[int] = 40
MAX_LINE_WIDTH_STEP: Final[int] = 1

LLM_CONCURRENCY_MIN: Final[int] = 1
LLM_CONCURRENCY_MAX: Final[int] = 50
LLM_CONCURRENCY_DEFAULT: Final[int] = 5
LLM_CONCURRENCY_STEP: Final[int] = 1

LLM_CHUNK_SIZE_MIN: Final[int] = 5
LLM_CHUNK_SIZE_MAX: Final[int] = 200
LLM_CHUNK_SIZE_DEFAULT: Final[int] = 30
LLM_CHUNK_SIZE_STEP: Final[int] = 5


# ==============================================================================
# 枚举定义
# ==============================================================================
class SubtitleFormat(str, Enum):
    """支持的字幕输出格式枚举。"""

    SRT = "srt"
    VTT = "vtt"
    TXT = "txt"
    JSON = "json"
    LRC = "lrc"
    ASS = "ass"
    WORD_SRT = "word_srt"
    CHAR_SRT = "char_srt"


class TaskType(str, Enum):
    """大模型任务类型枚举。"""

    TRANSLATE = "translate"
    SEGMENT = "segment"


class SupportedLanguage(str, Enum):
    """界面与模型支持的语言标识枚举。"""

    ZH = "zh"
    EN = "en"
    JA = "ja"
    KO = "ko"
