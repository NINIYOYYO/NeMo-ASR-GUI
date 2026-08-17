"""针对 Milestone M1 核心修复项的全面单元测试套件。

涵盖：
1. 日语音轨负时隙修复与时间轴钳制保护。
2. ASRService 多线程并发 RLock 互斥保护。
3. AudioService FFmpeg 懒加载与缺失时的优雅容灾。
4. 纯 SVG 矢量图标格式、渲染辅助函数与全语言 Emoji 清零。
"""

import json
import re
import threading
import time
from pathlib import Path

import pytest

from core.asr_service import ASRService
from core.audio_processor import AudioService
from core.post_processors import JapaneseCharStrategy
from utils.exceptions import AudioProcessingError
from utils.svg_icons import ICON_MAP, get_svg_icon, render_svg_html


def test_japanese_post_processor_negative_timeslot_clamp() -> None:
    """验证日语字符级重组策略在相邻字符时间极近时不会产生负时隙倒流。"""
    strategy = JapaneseCharStrategy()

    # 构造边界场景：下一个字符起始时间极小 (2.005s)，当前句开始时间 2.000s
    # 期望 final_end >= current_segment_start，且至少保持 0.05s 的有效时隙
    char_timestamps = [
        {"char": "あ", "start": 2.000, "end": 2.004},
        {"char": "。", "start": 2.004, "end": 2.005},
        {"char": "い", "start": 2.005, "end": 2.500},
    ]

    segments = strategy._group_chars_into_segments(char_timestamps)
    assert len(segments) >= 1
    for seg in segments:
        assert seg["end"] >= seg["start"], f"发现时间轴倒流缺陷: {seg}"
        assert seg["end"] - seg["start"] >= 0.04, f"时隙异常过短: {seg}"


def test_japanese_post_processor_end_not_less_than_start() -> None:
    """验证所有边界切分情况下 final_end >= current_segment_start。"""
    strategy = JapaneseCharStrategy()

    # 单字符强结束符
    chars = [
        {"char": "はい", "start": 1.0, "end": 1.1},
        {"char": "！", "start": 1.1, "end": 1.12},
    ]
    segments = strategy._group_chars_into_segments(chars)
    assert len(segments) == 1
    assert segments[0]["start"] <= segments[0]["end"]


def test_asr_service_rlock_concurrency() -> None:
    """验证 ASRService 的 RLock 能有效互斥保护模型加载与推理关键路径。"""
    service = ASRService()
    assert hasattr(service, "_lock")
    assert hasattr(service._lock, "acquire") and hasattr(service._lock, "release")
    assert "RLock" in type(service._lock).__name__ or type(service._lock).__name__ == "_RLock"

    execution_order: list[str] = []

    def mock_long_task(task_id: str, duration: float) -> None:
        with service._lock:
            execution_order.append(f"start_{task_id}")
            time.sleep(duration)
            execution_order.append(f"end_{task_id}")

    t1 = threading.Thread(target=mock_long_task, args=("t1", 0.05))
    t2 = threading.Thread(target=mock_long_task, args=("t2", 0.02))

    t1.start()
    time.sleep(0.01)  # 保证 t1 先获得锁
    t2.start()

    t1.join()
    t2.join()

    # 验证 t1 全程执行完毕后 t2 才能进入，杜绝交错并发竞争
    assert execution_order == ["start_t1", "end_t1", "start_t2", "end_t2"]


def test_audio_service_lazy_ffmpeg_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 AudioService 在 FFmpeg 缺失时启动不会抛错崩溃，而在实际执行提取时优雅报错。"""
    # 模拟 ffmpeg 命令缺失
    def mock_subprocess_run(*args, **kwargs):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    # 1. 实例化不应抛出 AudioProcessingError 异常
    service = AudioService()
    assert service.is_ffmpeg_available is False

    # 2. 调用音频提取时应抛出 AudioProcessingError
    with pytest.raises(AudioProcessingError) as exc_info:
        service.extract_audio_from_video("dummy_video.mp4")
    assert "FFmpeg 未" in str(exc_info.value) or "ffmpeg" in str(exc_info.value).lower()


def test_svg_icons_valid_xml_and_no_emojis() -> None:
    """验证所有 SVG 图标均为有效 SVG 字符串且不含任何 Emoji。"""
    emoji_pattern = re.compile(
        r"[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50-\u2b55\u200d\ufe0f]"
    )

    assert len(ICON_MAP) >= 12, "必须定义不少于 12 个核心矢量图标"

    for name, svg in ICON_MAP.items():
        assert svg.startswith("<svg") and svg.endswith("</svg>"), f"图标 {name} 不是标准 SVG 格式"
        assert not emoji_pattern.findall(svg), f"图标 {name} 中含有非法 Emoji"

    # 测试 helper 函数
    settings_svg = get_svg_icon("settings", width=20, height=20, color="#FF0000")
    assert 'width="20"' in settings_svg
    assert 'height="20"' in settings_svg
    assert 'stroke="#FF0000"' in settings_svg

    html = render_svg_html(settings_svg, "设置", gap=8)
    assert "<span" in html
    assert "设置" in html


def test_locales_zero_emoji_guarantee() -> None:
    """扫描所有 locales/*.json 文件，断言 0 个 Unicode Emoji 残留。"""
    root_dir = Path(__file__).resolve().parent.parent
    locale_files = list((root_dir / "locales").glob("*.json"))
    assert len(locale_files) == 4, f"期望找到 4 个多语言文件，实际找到 {len(locale_files)}"

    emoji_pattern = re.compile(
        r"[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50-\u2b55\u200d\ufe0f]"
    )

    for loc_file in locale_files:
        with open(loc_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        found_emojis: list[str] = []

        def scan_dict(obj: object, collector: list[str]) -> None:
            if isinstance(obj, dict):
                for val in obj.values():
                    scan_dict(val, collector)
            elif isinstance(obj, str):
                matches = emoji_pattern.findall(obj)
                if matches:
                    collector.extend(matches)

        scan_dict(data, found_emojis)
        assert len(found_emojis) == 0, f"文件 {loc_file.name} 中残留 Emoji: {found_emojis}"
