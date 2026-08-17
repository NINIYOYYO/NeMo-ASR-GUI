"""Milestone M3 规范与强类型测试套件。

验证：
1. core/constants.py 常量与枚举的完备性与正确性。
2. interfaces.py TypedDict 与返回类型的强类型约束。
3. 全仓函数与类 Google-style Docstring 规范达标与 Title Case 校验。
4. 全仓 Python 代码与 Docstring 零 Emoji 违规保护。
"""

import ast
import inspect
from pathlib import Path

from core.constants import (
    AUDIO_NORM_FACTOR,
    AVAILABLE_MODELS,
    CENTISECONDS_PER_SECOND,
    CHUNK_SLIDER_MAX,
    CHUNK_SLIDER_MIN,
    CHUNK_SLIDER_STEP,
    DEFAULT_AUDIO_CHANNELS,
    DEFAULT_CHUNK_DURATION_SEC,
    DEFAULT_CHUNK_LENGTH_MS,
    DEFAULT_CHUNK_LENGTH_S,
    DEFAULT_CLOUD_MODEL,
    DEFAULT_CONFIG_FILENAME,
    DEFAULT_CORRECTIONS_FILENAME,
    DEFAULT_LANGUAGE,
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_LLM_TIMEOUT_SEC,
    DEFAULT_LOG_BACKUP_COUNT,
    DEFAULT_LOG_FILENAME,
    DEFAULT_LOG_MAX_BYTES,
    DEFAULT_MAX_CHARS,
    DEFAULT_MAX_DURATION_SEC,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RATE_LIMIT_WAIT_SEC,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SEGMENTATION_CHUNK_SIZE,
    DEFAULT_SEGMENTATION_CONCURRENCY,
    DEFAULT_SLIDE_OVERLAP_SEC,
    DEFAULT_SOFT_LIMIT_CHARS,
    DEFAULT_TRANSLATION_CHUNK_SIZE,
    DEFAULT_TRANSLATION_CONCURRENCY,
    LLM_CHUNK_SIZE_DEFAULT,
    LLM_CHUNK_SIZE_MAX,
    LLM_CHUNK_SIZE_MIN,
    LLM_CHUNK_SIZE_STEP,
    LLM_CONCURRENCY_DEFAULT,
    LLM_CONCURRENCY_MAX,
    LLM_CONCURRENCY_MIN,
    LLM_CONCURRENCY_STEP,
    MAX_LINE_WIDTH_DEFAULT,
    MAX_LINE_WIDTH_MAX,
    MAX_LINE_WIDTH_MIN,
    MAX_LINE_WIDTH_STEP,
    MIN_JAPANESE_SEGMENT_DURATION_SEC,
    MIN_SEGMENT_DURATION_SEC,
    MS_PER_HOUR,
    MS_PER_MINUTE,
    MS_PER_SECOND,
    SECONDS_PER_HOUR,
    SECONDS_PER_MINUTE,
    SEGMENT_BOUNDARY_GUARD_SEC,
    SEGMENT_TOLERANCE_OFFSET_SEC,
    SILENCE_THRESHOLD_SEC,
    SPLIT_TOLERANCE_OFFSET_SEC,
    SubtitleFormat,
    SupportedLanguage,
    TaskType,
)
from core.subtitle_generator import SubtitleService
from interfaces import (
    CharTimestampDict,
    CorrectionEntry,
    SubtitleSegmentDict,
    WordTimestampDict,
)


def test_constants_audio_and_time_values():
    """验证音频与时间转换常量值与类型。"""
    assert DEFAULT_SAMPLE_RATE == 16000
    assert DEFAULT_AUDIO_CHANNELS == 1
    assert AUDIO_NORM_FACTOR == 32768.0
    assert DEFAULT_CHUNK_DURATION_SEC == 30.0
    assert DEFAULT_CHUNK_LENGTH_S == 60
    assert DEFAULT_CHUNK_LENGTH_MS == 60000
    assert DEFAULT_SLIDE_OVERLAP_SEC == 1.0

    assert MIN_SEGMENT_DURATION_SEC == 0.05
    assert SEGMENT_BOUNDARY_GUARD_SEC == 0.01
    assert SEGMENT_TOLERANCE_OFFSET_SEC == 0.05
    assert SPLIT_TOLERANCE_OFFSET_SEC == 0.02

    assert DEFAULT_MAX_DURATION_SEC == 8.0
    assert DEFAULT_MAX_CHARS == 40
    assert DEFAULT_SOFT_LIMIT_CHARS == 20
    assert SILENCE_THRESHOLD_SEC == 0.45
    assert MIN_JAPANESE_SEGMENT_DURATION_SEC == 0.5

    assert MS_PER_SECOND == 1000
    assert SECONDS_PER_MINUTE == 60
    assert SECONDS_PER_HOUR == 3600
    assert MS_PER_MINUTE == 60_000
    assert MS_PER_HOUR == 3600_000
    assert CENTISECONDS_PER_SECOND == 100


def test_constants_llm_and_ui_values():
    """验证 LLM、日志及 UI 范围常量。"""
    assert DEFAULT_LLM_TIMEOUT_SEC == 180.0
    assert DEFAULT_LLM_TEMPERATURE == 0.1
    assert DEFAULT_MAX_RETRIES == 3
    assert DEFAULT_RATE_LIMIT_WAIT_SEC == 20.0

    assert DEFAULT_TRANSLATION_CONCURRENCY == 5
    assert DEFAULT_TRANSLATION_CHUNK_SIZE == 30
    assert DEFAULT_SEGMENTATION_CONCURRENCY == 3
    assert DEFAULT_SEGMENTATION_CHUNK_SIZE == 50

    assert DEFAULT_LLM_BASE_URL == "https://api.openai.com/v1"
    assert DEFAULT_LLM_MODEL == "gpt-5.2"
    assert DEFAULT_CLOUD_MODEL == "nvidia/parakeet-tdt-0.6b-v2"
    assert DEFAULT_LANGUAGE == "zh"

    assert DEFAULT_LOG_MAX_BYTES == 5 * 1024 * 1024
    assert DEFAULT_LOG_BACKUP_COUNT == 5
    assert DEFAULT_LOG_FILENAME == "app.log"
    assert DEFAULT_CONFIG_FILENAME == "config.json"
    assert DEFAULT_CORRECTIONS_FILENAME == "corrections.json"

    assert CHUNK_SLIDER_MIN == 10
    assert CHUNK_SLIDER_MAX == 300
    assert CHUNK_SLIDER_STEP == 5

    assert MAX_LINE_WIDTH_MIN == 10
    assert MAX_LINE_WIDTH_MAX == 100
    assert MAX_LINE_WIDTH_DEFAULT == 40
    assert MAX_LINE_WIDTH_STEP == 1

    assert LLM_CONCURRENCY_MIN == 1
    assert LLM_CONCURRENCY_MAX == 50
    assert LLM_CONCURRENCY_DEFAULT == 5
    assert LLM_CONCURRENCY_STEP == 1

    assert LLM_CHUNK_SIZE_MIN == 5
    assert LLM_CHUNK_SIZE_MAX == 200
    assert LLM_CHUNK_SIZE_DEFAULT == 30
    assert LLM_CHUNK_SIZE_STEP == 5

    assert len(AVAILABLE_MODELS) >= 4
    assert "nvidia/parakeet-tdt-0.6b-v2" in AVAILABLE_MODELS


def test_enums_integrity():
    """验证 Enum 成员与对应字符串值。"""
    assert SubtitleFormat.SRT.value == "srt"
    assert SubtitleFormat.VTT.value == "vtt"
    assert SubtitleFormat.TXT.value == "txt"
    assert SubtitleFormat.JSON.value == "json"
    assert SubtitleFormat.LRC.value == "lrc"
    assert SubtitleFormat.ASS.value == "ass"
    assert SubtitleFormat.WORD_SRT.value == "word_srt"
    assert SubtitleFormat.CHAR_SRT.value == "char_srt"

    assert TaskType.TRANSLATE.value == "translate"
    assert TaskType.SEGMENT.value == "segment"

    assert SupportedLanguage.ZH.value == "zh"
    assert SupportedLanguage.EN.value == "en"
    assert SupportedLanguage.JA.value == "ja"
    assert SupportedLanguage.KO.value == "ko"


def test_typed_dict_structures():
    """验证 TypedDict 结构可在运行时正确构建与访问。"""
    char_item: CharTimestampDict = {"char": "a", "start": 0.1, "end": 0.2}
    word_item: WordTimestampDict = {"word": "test", "start": 0.1, "end": 0.5}
    seg: SubtitleSegmentDict = {
        "start": 0.1,
        "end": 0.5,
        "segment": "test",
        "index": 1,
        "chars": [char_item],
        "words": [word_item],
    }
    assert seg["start"] == 0.1
    assert seg["segment"] == "test"
    assert len(seg.get("chars", [])) == 1

    corr: CorrectionEntry = {"error": "erro", "correct": "error"}
    assert corr["error"] == "erro"


def test_format_time_returns_string_explicitly():
    """验证 format_time 签名与返回值恒定为 str。"""
    svc = SubtitleService()
    res = svc.format_time(12.345)
    assert isinstance(res, str)
    assert res == "00:00:12,345"

    sig = inspect.signature(svc.format_time)
    assert sig.return_annotation is str or sig.return_annotation == "str"


def test_zero_emoji_in_python_source_and_docstrings():
    """验证核心代码与 Docstring 中无任何 Unicode Emoji。"""
    root_dir = Path(__file__).resolve().parent.parent
    py_files = list(root_dir.glob("core/**/*.py")) + \
               list(root_dir.glob("controllers/**/*.py")) + \
               list(root_dir.glob("utils/**/*.py")) + \
               [root_dir / "application.py", root_dir / "app_ui.py", root_dir / "interfaces.py", root_dir / "main.py"]

    # 常见 Emoji 范围
    emoji_ranges = [
        (0x1F600, 0x1F64F),  # Emoticons
        (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs
        (0x1F680, 0x1F6FF),  # Transport and Map
        (0x1F700, 0x1F77F),  # Alchemical Symbols
        (0x1F780, 0x1F7FF),  # Geometric Shapes Extended
        (0x1F800, 0x1F8FF),  # Supplemental Arrows-C
        (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
        (0x1FA00, 0x1FA6F),  # Chess Symbols
        (0x1FA70, 0x1FAFF),  # Symbols and Pictographs Extended-A
        (0x2600, 0x26FF),    # Misc Symbols
        (0x2700, 0x27BF),    # Dingbats
    ]

    def has_emoji(text: str) -> bool:
        for ch in text:
            code = ord(ch)
            for start, end in emoji_ranges:
                if start <= code <= end:
                    return True
        return False

    for py_file in py_files:
        if not py_file.exists():
            continue
        content = py_file.read_text(encoding="utf-8")
        assert not has_emoji(content), f"文件 {py_file} 包含违规 Emoji 字符！"


def test_all_classes_and_public_functions_have_google_docstrings():
    """验证所有核心模块中的类与公开方法均具备标准 Google Docstrings，且无大写 ARGS: / RETURNS: 违规。"""
    root_dir = Path(__file__).resolve().parent.parent
    py_files = (
        list(root_dir.glob("core/**/*.py"))
        + list(root_dir.glob("controllers/**/*.py"))
        + list(root_dir.glob("utils/**/*.py"))
        + [
            root_dir / "application.py",
            root_dir / "app_ui.py",
            root_dir / "interfaces.py",
            root_dir / "main.py",
        ]
    )

    for py_file in py_files:
        if py_file.name == "__init__.py" or not py_file.exists():
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                doc = ast.get_docstring(node)
                # 检查文档注释存在
                assert (
                    doc is not None and len(doc.strip()) > 0
                ), f"文件 {py_file.name} 中 {node.name} 缺少 Docstring 文档注释"

                # 检查 Google 风格标签大小写规范 (不能是全大写 ARGS: / RETURNS: / YIELDS:)
                assert "ARGS:" not in doc, f"文件 {py_file.name} 中 {node.name} 使用了非标准大写 'ARGS:'，应为 'Args:'"
                assert "RETURNS:" not in doc, f"文件 {py_file.name} 中 {node.name} 使用了非标准大写 'RETURNS:'，应为 'Returns:'"
                assert "YIELDS:" not in doc, f"文件 {py_file.name} 中 {node.name} 使用了非标准大写 'YIELDS:'，应为 'Yields:'"
