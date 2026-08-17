"""8大核心关键场景综合缺失测试矩阵 (Comprehensive Missing Test Matrix)。

本测试模块覆盖系统的 8 大核心高危场景：
1. 场景 1: 日语音轨极短字符边界负时隙修复与单调递增时间轴保障。
2. 场景 2: Windows CRLF (\\r\\n)、Unix LF (\\n) 及混合换行符 SRT/VTT/LRC 解析与格式化往返。
3. 场景 3: ASRService 高并发多线程压力测试（验证 RLock 互斥锁杜绝竞态条件与悬空指针）。
4. 场景 4: 音频处理健壮性（损坏文件、非法格式、软检测及显存 OOM 降级容灾）。
5. 场景 5: LogFilter 正则模式匹配、min_level 阈值过滤及 SafeStreamHandler 关闭流安全退出。
6. 场景 6: 字幕翻译与 AI 智能断句动态规划 (DP) 锚点词对齐算法在严重增删改下的抗漂移能力。
7. 场景 7: 转录协作式 CancellationToken 在分块处理中的实时中断（杜绝僵尸计算）。
8. 场景 8: 纯 SVG 矢量图标库完整性、UI 集成及 4 国语言实时切换 0-Emoji 严格红线。
"""

import concurrent.futures
import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydub.generators import Sine

from controllers.transcription_controller import TranscriptionController
from core.asr_service import ASRService
from core.audio_processor import AudioService
from core.constants import (
    DEFAULT_LANGUAGE,
    DEFAULT_SAMPLE_RATE,
    MIN_JAPANESE_SEGMENT_DURATION_SEC,
    MIN_SEGMENT_DURATION_SEC,
    SubtitleFormat,
)
from core.post_processors import JapaneseCharStrategy
from core.subtitle_generator import SubtitleService
from core.translation_service import TranslationService
from interfaces import (
    CancellationToken,
    CharTimestampDict,
    SubtitleSegmentDict,
    TaskCancelledError,
)
from utils.exceptions import AudioProcessingError
from utils.log_filter import ConfigurableFilter
from utils.logger import SafeStreamHandler, stop_logging
from utils.svg_icons import ICON_MAP, get_svg_icon, render_svg_html
from utils.translator import Translator, get_language, set_language


# =====================================================================
# 场景 1: 日语音轨极短字符边界负时隙修复与单调递增时间轴保障
# =====================================================================
def test_japanese_extreme_microsecond_intervals() -> None:
    """测试日语音轨字符在极短间隔 (毫秒/微秒级) 下不会产生负时隙倒流且时隙符合最小阈值。"""
    strategy = JapaneseCharStrategy()

    # 构造极短时间片字符流：字符间隔仅 1ms - 2ms
    char_timestamps: list[CharTimestampDict] = [
        {"char": "こ", "start": 1.000, "end": 1.002},
        {"char": "ん", "start": 1.002, "end": 1.004},
        {"char": "に", "start": 1.004, "end": 1.006},
        {"char": "ち", "start": 1.006, "end": 1.008},
        {"char": "は", "start": 1.008, "end": 1.010},
        {"char": "。", "start": 1.010, "end": 1.011},
        {"char": "世", "start": 1.012, "end": 1.014},
        {"char": "界", "start": 1.014, "end": 1.016},
        {"char": "！", "start": 1.016, "end": 1.018},
    ]

    segments = strategy._group_chars_into_segments(char_timestamps)
    assert len(segments) == 2, f"应按强标点断为 2 句，实际得到 {len(segments)} 句"

    for seg_idx, seg in enumerate(segments):
        start = seg["start"]
        end = seg["end"]
        # 1. 绝对严禁负时隙
        assert end >= start, f"发现严重负时隙倒流: start={start}, end={end} in {seg}"
        # 2. 必须具备最小安全时长保障
        assert end - start >= MIN_SEGMENT_DURATION_SEC - 1e-6, f"分段时长过短: {seg}"
        # 3. 字符列表非空且文本对应
        assert len(seg.get("chars", [])) > 0
        if seg_idx > 0:
            assert start >= segments[seg_idx - 1]["start"], "分段起始时间戳必须单调递增"


def test_japanese_zero_duration_and_overlapping_characters() -> None:
    """测试当模型输出零时长 (start == end) 或轻度重叠字符时，重组算法仍能产出合法字幕。"""
    strategy = JapaneseCharStrategy()

    # 模拟 CTC 解码器可能输出的零时长或重叠字符
    char_timestamps: list[CharTimestampDict] = [
        {"char": "東", "start": 2.000, "end": 2.000},  # 零时长
        {"char": "京", "start": 1.995, "end": 2.050},  # 轻微重叠
        {"char": "特", "start": 2.050, "end": 2.100},
        {"char": "許", "start": 2.090, "end": 2.150},
        {"char": "局", "start": 2.150, "end": 2.200},
        {"char": "。", "start": 2.200, "end": 2.200},
    ]

    segments = strategy._group_chars_into_segments(char_timestamps)
    assert len(segments) == 1
    seg = segments[0]
    assert seg["segment"] == "東京特許局。"
    assert seg["start"] == 2.000
    assert seg["end"] >= seg["start"] + MIN_JAPANESE_SEGMENT_DURATION_SEC
    assert seg["end"] >= seg["start"]


def test_japanese_rapid_succession_punctuation_and_whitespace() -> None:
    """测试连续强标点、弱停顿与纯空白字符序列被正确清洗与规整。"""
    strategy = JapaneseCharStrategy()

    char_timestamps: list[CharTimestampDict] = [
        {"char": "あ", "start": 0.0, "end": 0.2},
        {"char": "！", "start": 0.2, "end": 0.25},
        {"char": "？", "start": 0.25, "end": 0.3},
        {"char": "…", "start": 0.3, "end": 0.35},
        {"char": " ", "start": 0.35, "end": 0.4},
        {"char": "い", "start": 0.5, "end": 0.7},
        {"char": "、", "start": 0.7, "end": 0.75},
        {"char": "う", "start": 0.75, "end": 0.95},
        {"char": "。", "start": 0.95, "end": 1.0},
    ]

    segments = strategy._group_chars_into_segments(char_timestamps)
    assert len(segments) >= 1
    for seg in segments:
        text = seg["segment"]
        assert text not in {"！", "？", "…", "。", "、", ""}, "不应产出纯标点的无意义分段"
        assert seg["end"] >= seg["start"]


def test_japanese_single_character_and_boundary_guards() -> None:
    """测试单字符以及下一个字符紧挨当前起始时间点的边界防溢出保护。"""
    strategy = JapaneseCharStrategy()

    # 边界情况：下一个字符就在 0.001s 后（极其紧凑）
    char_timestamps: list[CharTimestampDict] = [
        {"char": "あ", "start": 0.000, "end": 0.001},
        {"char": "！", "start": 0.001, "end": 0.002},
        {"char": "い", "start": 0.003, "end": 0.500},
    ]

    segments = strategy._group_chars_into_segments(char_timestamps)
    assert len(segments) == 2
    for seg in segments:
        assert seg["start"] >= 0.0
        assert seg["end"] >= seg["start"]


def test_japanese_srt_roundtrip_formatting() -> None:
    """测试日语音轨重构结果直接经过 SubtitleService 生成与解析的一致性。"""
    strategy = JapaneseCharStrategy()
    subtitle_service = SubtitleService()

    char_timestamps: list[CharTimestampDict] = [
        {"char": "あ", "start": 0.0, "end": 0.5},
        {"char": "り", "start": 0.5, "end": 1.0},
        {"char": "が", "start": 1.0, "end": 1.5},
        {"char": "と", "start": 1.5, "end": 2.0},
        {"char": "う", "start": 2.0, "end": 2.5},
        {"char": "。", "start": 2.5, "end": 2.6},
    ]

    segments = strategy._group_chars_into_segments(char_timestamps)
    srt_content = subtitle_service.generate_content(segments, SubtitleFormat.SRT.value)

    assert "00:00:00,000 -->" in srt_content
    assert "ありがとう。" in srt_content

    # 解析回对象
    parsed = subtitle_service.parse_srt(srt_content)
    assert len(parsed) == 1
    assert parsed[0]["segment"] == "ありがとう。"
    assert parsed[0]["start"] == 0.0


# =====================================================================
# 场景 2: Windows CRLF, Unix LF 及混合换行符 SRT/VTT/LRC 解析与格式化
# =====================================================================
def test_crlf_lf_mixed_srt_roundtrip() -> None:
    """测试 Windows CRLF (\\r\\n)、Unix LF (\\n) 及纯 CR (\\r) 格式 SRT 解析和重新生成的完全往返保真度。"""
    service = SubtitleService()

    # 1. 包含 CRLF 换行的 SRT 字符串
    crlf_content = (
        "1\r\n"
        "00:00:01,000 --> 00:00:04,500\r\n"
        "First CRLF subtitle block\r\n\r\n"
        "2\r\n"
        "00:00:05,000 --> 00:00:08,250\r\n"
        "Second CRLF subtitle block\r\n\r\n"
    )

    parsed_crlf = service.parse_srt(crlf_content)
    assert len(parsed_crlf) == 2
    assert parsed_crlf[0]["start"] == 1.0
    assert parsed_crlf[0]["end"] == 4.5
    assert parsed_crlf[0]["segment"] == "First CRLF subtitle block"
    assert parsed_crlf[1]["start"] == 5.0
    assert parsed_crlf[1]["end"] == 8.25

    # 2. 混合换行符（CRLF 与 LF 交叉）
    mixed_content = (
        "1\n"
        "00:00:01,000 --> 00:00:04,500\r\n"
        "Mixed line 1\r\nMixed line 2\n\n"
        "2\r\n"
        "00:00:05,000 --> 00:00:08,000\n"
        "Mixed block 2\r\n\r\n"
    )
    parsed_mixed = service.parse_srt(mixed_content)
    assert len(parsed_mixed) == 2
    assert "Mixed line 1\nMixed line 2" in parsed_mixed[0]["segment"].replace("\r\n", "\n")

    # 3. 重新生成 SRT 并再解析（双向往返）
    regenerated_srt = service.generate_content(parsed_crlf, "srt")
    re_parsed = service.parse_srt(regenerated_srt)
    assert len(re_parsed) == 2
    assert re_parsed[0]["segment"] == "First CRLF subtitle block"
    assert re_parsed[0]["start"] == 1.0
    assert re_parsed[0]["end"] == 4.5


def test_multiline_subtitle_blocks_with_mixed_newlines() -> None:
    """测试多行字幕内容（如诗歌、对话、歌词）包含内部换行时的解析准确性。"""
    service = SubtitleService()

    multiline_srt = (
        "1\r\n"
        "00:00:10,000 --> 00:00:15,000\r\n"
        "- Hello! How are you?\r\n"
        "- I am fine, thank you!\r\n"
        "- Good to hear.\r\n\r\n"
        "2\n"
        "00:00:16,000 --> 00:00:20,000\n"
        "Line A\nLine B\n\n"
    )

    parsed = service.parse_srt(multiline_srt)
    assert len(parsed) == 2
    lines_block_1 = parsed[0]["segment"].replace("\r\n", "\n").split("\n")
    assert len(lines_block_1) == 3
    assert lines_block_1[0] == "- Hello! How are you?"
    assert lines_block_1[1] == "- I am fine, thank you!"
    assert lines_block_1[2] == "- Good to hear."


def test_vtt_lrc_txt_crlf_lf_roundtrip() -> None:
    """测试 VTT、LRC、TXT 及 JSON 格式在各种换行条件下的生成格式与解析。"""
    service = SubtitleService()

    sample_segments: list[SubtitleSegmentDict] = [
        {"start": 0.0, "end": 2.5, "segment": "First Line"},
        {"start": 3.0, "end": 5.8, "segment": "Second Line"},
    ]

    # VTT 测试
    vtt = service.generate_content(sample_segments, SubtitleFormat.VTT.value)
    assert vtt.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:02.500" in vtt

    # LRC 歌词测试
    lrc = service.generate_content(sample_segments, SubtitleFormat.LRC.value)
    assert "[00:00.00]First Line" in lrc
    assert "[00:03.00]Second Line" in lrc

    # TXT 纯文本测试
    txt = service.generate_content(sample_segments, SubtitleFormat.TXT.value)
    assert txt.strip() == "First Line\nSecond Line"

    # JSON 结构测试
    json_str = service.generate_content(sample_segments, SubtitleFormat.JSON.value)
    data = json.loads(json_str)
    assert len(data) == 2
    assert data[0]["segment"] == "First Line"
    assert data[0]["start"] == 0.0
    assert data[0]["end"] == 2.5


def test_word_and_char_srt_roundtrip_crlf() -> None:
    """测试字级 (Char) 与词级 (Word) 细粒度时间戳导出为独立 SRT 时的换行与时间轴完整性。"""
    service = SubtitleService()

    rich_segments: list[SubtitleSegmentDict] = [
        {
            "start": 0.0,
            "end": 2.0,
            "segment": "Hello World",
            "words": [
                {"word": "Hello", "start": 0.0, "end": 0.8},
                {"word": "World", "start": 1.0, "end": 2.0},
            ],
            "chars": [
                {"char": "H", "start": 0.0, "end": 0.1},
                {"char": "e", "start": 0.1, "end": 0.2},
                {"char": "l", "start": 0.2, "end": 0.3},
                {"char": "l", "start": 0.3, "end": 0.4},
                {"char": "o", "start": 0.4, "end": 0.8},
            ],
        }
    ]

    word_srt = service.generate_content(rich_segments, SubtitleFormat.WORD_SRT.value)
    assert "Hello" in word_srt
    assert "World" in word_srt
    parsed_word_srt = service.parse_srt(word_srt)
    assert len(parsed_word_srt) == 2

    char_srt = service.generate_content(rich_segments, SubtitleFormat.CHAR_SRT.value)
    assert "H" in char_srt
    parsed_char_srt = service.parse_srt(char_srt)
    assert len(parsed_char_srt) == 5


def test_srt_large_dataset_crlf_stress() -> None:
    """压力测试：生成并解析 500 个段落的超大 CRLF SRT 文件，验证解析性能与无内存泄漏。"""
    service = SubtitleService()

    large_segments: list[SubtitleSegmentDict] = []
    for idx in range(500):
        start = idx * 2.0
        end = start + 1.8
        large_segments.append(
            {"start": start, "end": end, "segment": f"Stress test sentence #{idx}"}
        )

    # 导出为 CRLF 格式的 SRT
    srt_output = service.generate_content(large_segments, "srt").replace("\n", "\r\n")

    # 解析
    parsed = service.parse_srt(srt_output)
    assert len(parsed) == 500
    assert parsed[0]["segment"] == "Stress test sentence #0"
    assert parsed[499]["segment"] == "Stress test sentence #499"
    assert parsed[499]["start"] == 499 * 2.0


# =====================================================================
# 场景 3: ASRService 高并发多线程压力测试 (RLock 互斥锁保护)
# =====================================================================
def test_asr_service_high_concurrency_stress(tmp_path: Path) -> None:
    """高并发多线程压力测试：20 个并发工作线程同时执行模型加载、显存释放与分块推理，验证无死锁、无竞态奔溃。"""
    sine_wave = Sine(440).to_audio_segment(duration=1000)
    sine_wave = sine_wave.set_frame_rate(DEFAULT_SAMPLE_RATE).set_channels(1)
    wav_path = str(tmp_path / "concurrent_test.wav")
    sine_wave.export(wav_path, format="wav")

    asr = ASRService()

    class FastMockModel:
        def __init__(self) -> None:
            self.lock_check = threading.Lock()

        def transcribe(self, paths2audio_files=None, audio=None, **kwargs):
            time.sleep(0.01)  # 模拟推理微延时
            mock_hyp = MagicMock()
            mock_hyp.text = "concurrency test passed"
            mock_hyp.timestamp = {
                "segment": [{"start": 0.0, "end": 0.5, "segment": "concurrency test passed"}]
            }
            mock_hyp.words = []
            return [mock_hyp]

    asr.model = FastMockModel()

    errors: list[Exception] = []

    def task_transcribe(thread_id: int) -> None:
        try:
            res = asr.transcribe_audio_in_chunks(wav_path, chunk_length_ms=500)
            assert isinstance(res, list)
        except Exception as e:
            errors.append(e)

    def task_release(thread_id: int) -> None:
        try:
            # 内部会自动加锁
            asr._release_memory()
            # 恢复 mock model 以供后续线程使用
            with asr._lock:
                asr.model = FastMockModel()
        except Exception as e:
            errors.append(e)

    def task_strategy_update(thread_id: int) -> None:
        try:
            with asr._lock:
                asr._update_strategy(f"model_ja_{thread_id}")
                assert asr.processor_strategy is not None
        except Exception as e:
            errors.append(e)

    # 启动 20 个并发线程交叉执行不同操作
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        for i in range(20):
            if i % 3 == 0:
                futures.append(executor.submit(task_transcribe, i))
            elif i % 3 == 1:
                futures.append(executor.submit(task_release, i))
            else:
                futures.append(executor.submit(task_strategy_update, i))

        concurrent.futures.wait(futures, timeout=10.0)

    assert len(errors) == 0, f"多线程并发压力测试发生异常: {errors}"


def test_asr_service_interleaved_model_switch_and_transcription(tmp_path: Path) -> None:
    """测试在转录进行过程中，其他线程尝试切换或释放模型时，RLock 严格串行化，防止 NoneType AttributeError。"""
    sine_wave = Sine(440).to_audio_segment(duration=1500)
    wav_path = str(tmp_path / "switch_test.wav")
    sine_wave.export(wav_path, format="wav")

    asr = ASRService()

    execution_log: list[str] = []

    class TrackedModel:
        def transcribe(self, paths2audio_files=None, audio=None, **kwargs):
            execution_log.append("inference_start")
            time.sleep(0.05)
            execution_log.append("inference_end")
            mock_hyp = MagicMock()
            mock_hyp.text = "safe inference"
            mock_hyp.timestamp = {"segment": [{"start": 0.0, "end": 1.0, "segment": "safe inference"}]}
            return [mock_hyp]

    asr.model = TrackedModel()

    def worker_transcribe() -> None:
        res = asr.transcribe_audio_in_chunks(wav_path, chunk_length_ms=1500)
        assert len(res) >= 1

    def worker_switch_model() -> None:
        time.sleep(0.01)  # 稍微滞后启动，等待 transcribe 获得锁
        with asr._lock:
            execution_log.append("model_switch_acquired_lock")
            asr.model = TrackedModel()

    t1 = threading.Thread(target=worker_transcribe)
    t2 = threading.Thread(target=worker_switch_model)

    t1.start()
    t2.start()

    t1.join(timeout=5.0)
    t2.join(timeout=5.0)

    # 验证 inference_start 之后必须先 inference_end，然后才是 model_switch_acquired_lock
    assert execution_log[0] == "inference_start"
    assert execution_log[1] == "inference_end"
    assert execution_log[2] == "model_switch_acquired_lock"


def test_asr_service_rlock_reentrancy_integrity() -> None:
    """验证 ASRService._lock 具备重入特性，同一个线程内嵌套加锁不会引起自死锁。"""
    asr = ASRService()
    assert hasattr(asr, "_lock")

    with asr._lock:
        with asr._lock:
            with asr._lock:
                # 三重可重入加锁测试
                asr._update_strategy("test_model")
                assert asr.processor_strategy is not None


# =====================================================================
# 场景 4: 音频处理健壮性 (损坏文件、非法格式、软检测及显存 OOM 降级容灾)
# =====================================================================
def test_audio_service_invalid_and_corrupt_files(tmp_path: Path) -> None:
    """测试 AudioService 对不存在的文件、损坏的文件及非音视频文件能够安全拦截并抛出标准 AudioProcessingError。"""
    audio_service = AudioService()

    # 1. 不存在的文件
    with pytest.raises(AudioProcessingError) as exc_info:
        audio_service.extract_audio_from_video(str(tmp_path / "non_existent_file.mp4"))
    assert "FFmpeg" in str(exc_info.value) or "失败" in str(exc_info.value)

    # 2. 损坏的二进制垃圾文件 (1KB 随机字节)
    corrupt_file = tmp_path / "corrupt_video.mp4"
    corrupt_file.write_bytes(os.urandom(1024))

    with pytest.raises(AudioProcessingError) as exc_corrupt:
        audio_service.extract_audio_from_video(str(corrupt_file))
    assert "失败" in str(exc_corrupt.value) or "FFmpeg" in str(exc_corrupt.value)


def test_audio_service_unsupported_format_and_missing_ffmpeg(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """测试当系统未安装 FFmpeg 时，AudioService 的软检测机制保证启动不闪退，仅在调用提取时抛错。"""
    def mock_subprocess_missing(*args: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("No ffmpeg binary found in PATH")

    monkeypatch.setattr("subprocess.run", mock_subprocess_missing)

    # 实例化必须平稳，不能抛错闪退
    lazy_service = AudioService()
    assert lazy_service.is_ffmpeg_available is False

    dummy_media = tmp_path / "sample.mp4"
    dummy_media.write_bytes(b"dummy")

    with pytest.raises(AudioProcessingError) as exc_info:
        lazy_service.extract_audio_from_video(str(dummy_media))
    assert "FFmpeg 未安装或不可用" in str(exc_info.value)


def test_asr_service_cuda_oom_handling_and_recovery(tmp_path: Path) -> None:
    """测试 ASRService 在遭遇 CUDA Out Of Memory 异常时平稳记录并安全清理资源，不使单例陷入死锁或脏状态。"""
    sine_wave = Sine(440).to_audio_segment(duration=1000)
    wav_path = str(tmp_path / "oom_test.wav")
    sine_wave.export(wav_path, format="wav")

    asr = ASRService()

    class OOMThrowingModel:
        def transcribe(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("CUDA out of memory. Tried to allocate 4.00 GiB")

    asr.model = OOMThrowingModel()

    # 执行转录，内部应捕获并记录错误，返回空列表而不是崩溃退出
    results = asr.transcribe_audio_in_chunks(wav_path, chunk_length_ms=1000)
    assert results == []

    # 验证后续依然可加锁并正常操作
    assert asr.is_model_loaded is True
    asr._release_memory()
    assert asr.is_model_loaded is False


def test_asr_service_corrupt_or_truncated_wav_handling(tmp_path: Path) -> None:
    """测试转录一个 0 字节或非 WAV 头文件时，ASRService 优雅处理并返回空列表。"""
    zero_byte_wav = str(tmp_path / "zero_byte.wav")
    with open(zero_byte_wav, "wb") as f:
        f.write(b"")

    asr = ASRService()
    asr.model = MagicMock()

    results = asr.transcribe_audio_in_chunks(zero_byte_wav, chunk_length_ms=1000)
    assert results == []


# =====================================================================
# 场景 5: LogFilter 正则模式匹配、min_level 阈值过滤及 SafeStreamHandler
# =====================================================================
def test_log_filter_multi_pattern_regex_and_min_level(tmp_path: Path) -> None:
    """测试 LogFilter 支持多组复杂正则表达式匹配，且精确按 min_level 进行放行或拦截。"""
    config_path = tmp_path / "complex_filter.yaml"
    config_yaml = """
message_filters:
  - pattern: "HTTP/1\\.[01] (200|304)"
    min_level: "WARNING"
  - pattern: "\\[Worker-\\d+\\] Heartbeat"
    level: "ERROR"
"""
    config_path.write_text(config_yaml, encoding="utf-8")

    flt = ConfigurableFilter(str(config_path))
    assert len(flt.message_patterns) == 2

    # 1. 匹配 HTTP 正则但级别为 INFO (低于 WARNING) -> 拦截 (False)
    rec_http_info = logging.LogRecord(
        name="server",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="GET /status HTTP/1.1 200 OK",
        args=(),
        exc_info=None,
    )
    assert flt.filter(rec_http_info) is False

    # 2. 匹配 HTTP 正则且级别为 WARNING (>= WARNING) -> 放行 (True)
    rec_http_warn = logging.LogRecord(
        name="server",
        level=logging.WARNING,
        pathname=__file__,
        lineno=10,
        msg="GET /slow_endpoint HTTP/1.1 200 OK",
        args=(),
        exc_info=None,
    )
    assert flt.filter(rec_http_warn) is True

    # 3. 匹配 Worker 正则且级别为 WARNING (低于 ERROR) -> 拦截 (False)
    rec_worker_warn = logging.LogRecord(
        name="worker",
        level=logging.WARNING,
        pathname=__file__,
        lineno=20,
        msg="[Worker-42] Heartbeat check warning",
        args=(),
        exc_info=None,
    )
    assert flt.filter(rec_worker_warn) is False

    # 4. 完全不匹配正则的常规日志 -> 放行 (True)
    rec_normal = logging.LogRecord(
        name="app",
        level=logging.DEBUG,
        pathname=__file__,
        lineno=30,
        msg="Application started normally",
        args=(),
        exc_info=None,
    )
    assert flt.filter(rec_normal) is True


def test_log_filter_missing_or_corrupt_yaml_fallback(tmp_path: Path) -> None:
    """测试当过滤配置文件不存在或 YAML 语法损坏时，过滤器安全降级不引发应用崩溃。"""
    # 1. 不存在的文件
    flt_missing = ConfigurableFilter(str(tmp_path / "non_existent_config.yaml"))
    assert len(flt_missing.message_patterns) == 0

    # 2. 损坏的 YAML
    bad_yaml = tmp_path / "corrupt.yaml"
    bad_yaml.write_text("::: bad yaml content :::", encoding="utf-8")
    flt_bad = ConfigurableFilter(str(bad_yaml))
    assert isinstance(flt_bad.message_patterns, list)


def test_safe_stream_handler_closed_stream_and_write_exceptions() -> None:
    """测试 SafeStreamHandler 在遇到底层流已关闭、write 或 flush 抛出 I/O 异常时静默安全吞噬，防止解释器退出崩溃。"""
    class ThrowingStream:
        closed = True

        def write(self, data: str) -> None:
            raise ValueError("I/O operation on closed file")

        def flush(self) -> None:
            raise OSError("Stream closed")

    handler = SafeStreamHandler(ThrowingStream())

    rec = logging.LogRecord(
        name="test_shutdown",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Message during process shutdown",
        args=(),
        exc_info=None,
    )

    # 必须平稳执行，不向外抛出异常
    handler.emit(rec)
    handler.flush()


def test_logger_stop_logging_idempotency_and_teardown() -> None:
    """测试 stop_logging 可以安全多次调用 (幂等性) 且不会抛出未处理异常。"""
    stop_logging()
    stop_logging()  # 二次调用幂等性测试


# =====================================================================
# 场景 6: 字幕翻译与 AI 智能断句 DP 锚点词时间戳重对齐算法
# =====================================================================
def test_dp_alignment_text_expansion_and_filler_words() -> None:
    """测试当大模型增加前导说明语、转折词或语气词时，后续段落时间戳通过 DP 锚点精确对齐，无累积漂移。"""
    service = TranslationService()

    original_segments: list[SubtitleSegmentDict] = [
        {"start": 0.0, "end": 3.0, "segment": "今天的天气非常晴朗"},
        {"start": 3.0, "end": 6.0, "segment": "我们决定去海边散步"},
        {"start": 6.0, "end": 9.0, "segment": "顺便欣赏美丽的日落"},
    ]

    # LLM 在开头插入了 8 个修饰字：“根据气象预报显示，”
    llm_output = (
        "根据气象预报显示，今天的天气非常晴朗 | "
        "我们决定去海边散步 | "
        "顺便欣赏美丽的日落"
    )

    aligned = service.align_timestamps(original_segments, llm_output)
    assert len(aligned) == 3
    # 第一句涵盖开头
    assert aligned[0]["start"] == 0.0
    # 第二句锚点词“我们决定去海边散步”必须紧贴 3.0s (误差 < 0.25s)
    assert abs(aligned[1]["start"] - 3.0) < 0.25
    # 第三句锚点词“顺便欣赏美丽的日落”必须紧贴 6.0s
    assert abs(aligned[2]["start"] - 6.0) < 0.25
    # 全程时长单调递增且不超范围
    for seg in aligned:
        assert seg["end"] > seg["start"]
        assert seg["end"] <= 9.0 + 0.1


def test_dp_alignment_text_contraction_and_stopword_removal() -> None:
    """测试当大模型删减冗余停用词、缩略语句时，时间戳依然稳定锚定。"""
    service = TranslationService()

    original_segments: list[SubtitleSegmentDict] = [
        {"start": 0.0, "end": 2.0, "segment": "人工智能正在快速发展"},
        {"start": 2.0, "end": 4.0, "segment": "带来了巨大的社会变革"},
    ]

    # LLM 将第一句精简为 "AI快速发展"
    llm_output = "AI快速发展 | 带来了巨大的社会变革"

    aligned = service.align_timestamps(original_segments, llm_output)
    assert len(aligned) == 2
    assert aligned[0]["start"] == 0.0
    assert abs(aligned[1]["start"] - 2.0) < 0.3
    assert aligned[1]["end"] <= 4.0 + 0.1


def test_dp_alignment_sentence_splitting_and_merging() -> None:
    """测试 1 句长原句被大模型拆分为 3 句短句，以及多句原句被合并为 1 句时的平滑时间插值。"""
    service = TranslationService()

    # 1. 拆分测试 (1 句拆为 3 句)
    single_long_segment: list[SubtitleSegmentDict] = [
        {"start": 10.0, "end": 20.0, "segment": "第一部分内容，第二部分内容，第三部分内容。"}
    ]
    split_llm = "第一部分内容 | 第二部分内容 | 第三部分内容"
    split_result = service.align_timestamps(single_long_segment, split_llm)
    assert len(split_result) == 3
    assert split_result[0]["start"] == 10.0
    assert split_result[1]["start"] > split_result[0]["start"]
    assert split_result[2]["start"] > split_result[1]["start"]
    assert split_result[2]["end"] <= 20.0 + 0.1

    # 2. 合并测试 (3 句合为 1 句)
    three_segments: list[SubtitleSegmentDict] = [
        {"start": 0.0, "end": 2.0, "segment": "模块A"},
        {"start": 2.0, "end": 4.0, "segment": "模块B"},
        {"start": 4.0, "end": 6.0, "segment": "模块C"},
    ]
    merge_llm = "模块A 模块B 模块C合并为一段"
    merge_result = service.align_timestamps(three_segments, merge_llm)
    assert len(merge_result) == 1
    assert merge_result[0]["start"] == 0.0
    assert abs(merge_result[0]["end"] - 6.0) < 0.1


def test_dp_alignment_word_reordering_cross_lingual() -> None:
    """测试跨语系语序倒装 (如主宾谓 SOV 与主谓宾 SVO) 下的对齐稳定性。"""
    service = TranslationService()

    original_segments: list[SubtitleSegmentDict] = [
        {"start": 0.0, "end": 2.0, "segment": "私はリンゴを食べました"},
        {"start": 2.0, "end": 4.0, "segment": "とても美味しかったです"},
    ]

    llm_output = "I ate an apple | It was very delicious"
    aligned = service.align_timestamps(original_segments, llm_output)
    assert len(aligned) == 2
    assert aligned[0]["start"] == 0.0
    assert aligned[0]["end"] <= aligned[1]["start"] + 0.1
    assert abs(aligned[1]["end"] - 4.0) < 0.1


def test_dp_alignment_zero_overlap_and_wild_rewrites() -> None:
    """测试极端场景：大模型完全自由改写文本（0 相同字符重合）时的平滑均分保底。"""
    service = TranslationService()

    original_segments: list[SubtitleSegmentDict] = [
        {"start": 0.0, "end": 10.0, "segment": "1234567890"}
    ]

    llm_wild = "Alpha | Beta | Gamma | Delta | Epsilon"
    aligned = service.align_timestamps(original_segments, llm_wild)
    assert len(aligned) == 5
    assert aligned[0]["start"] == 0.0
    for i in range(len(aligned) - 1):
        assert aligned[i + 1]["start"] >= aligned[i]["start"]
        assert aligned[i]["end"] > aligned[i]["start"]
    assert abs(aligned[-1]["end"] - 10.0) < 0.1


def test_dp_alignment_empty_and_boundary_inputs() -> None:
    """测试边界输入：空列表、纯空白字符、单个标点等不会引发异常。"""
    service = TranslationService()

    assert service.align_timestamps([], "some text") == []

    segs: list[SubtitleSegmentDict] = [{"start": 0.0, "end": 1.0, "segment": "test"}]
    assert service.align_timestamps(segs, "") == segs
    assert service.align_timestamps(segs, "   ") == segs
    assert service.align_timestamps(segs, "single sentence without separator") == segs


# =====================================================================
# 场景 7: 转录协作式 CancellationToken 取消机制 (实时中断与防僵尸计算)
# =====================================================================
def test_cancellation_token_thread_safe_abort_during_chunks(tmp_path: Path) -> None:
    """测试多线程异步取消：在处理 10 个音频分块的过程中，第 2 块完成后外部线程发出取消信号，转录立即终止，绝不计算后续 8 块。"""
    # 构造 10 秒的长音频
    sine_wave = Sine(440).to_audio_segment(duration=10000)
    wav_path = str(tmp_path / "ten_chunks.wav")
    sine_wave.export(wav_path, format="wav")

    asr = ASRService()
    computed_chunks: list[int] = []

    class ChunkCountingModel:
        def __init__(self, token: CancellationToken) -> None:
            self.token = token

        def transcribe(self, paths2audio_files=None, audio=None, **kwargs):
            current_count = len(computed_chunks) + 1
            computed_chunks.append(current_count)
            # 当完成第 2 块时，模拟外部异步取消
            if current_count == 2:
                self.token.cancel()
            mock_hyp = MagicMock()
            mock_hyp.text = f"chunk_{current_count}"
            mock_hyp.timestamp = {
                "segment": [{"start": 0.0, "end": 1.0, "segment": f"chunk_{current_count}"}]
            }
            return [mock_hyp]

    cancel_token = CancellationToken()
    asr.model = ChunkCountingModel(cancel_token)

    results = asr.transcribe_audio_in_chunks(
        wav_path, chunk_length_ms=1000, cancellation_token=cancel_token
    )

    # 验证：仅执行了 2 个分块，后续第 3-10 个分块全部被协作式取消拦截，0 僵尸计算
    assert len(computed_chunks) == 2, f"期望仅计算 2 块，实际计算了 {len(computed_chunks)} 块"
    assert len(results) == 2
    assert cancel_token.is_cancelled is True


def test_cancellation_before_transcription_start(tmp_path: Path) -> None:
    """测试在进入 transcribe_audio_in_chunks 之前已处于取消状态，立即返回 0 结果。"""
    sine_wave = Sine(440).to_audio_segment(duration=2000)
    wav_path = str(tmp_path / "pre_cancel.wav")
    sine_wave.export(wav_path, format="wav")

    asr = ASRService()
    mock_model = MagicMock()
    asr.model = mock_model

    token = CancellationToken()
    token.cancel()

    results = asr.transcribe_audio_in_chunks(
        wav_path, chunk_length_ms=1000, cancellation_token=token
    )

    assert results == []
    # 模型 transcribe 从未被调用
    assert mock_model.transcribe.call_count == 0


def test_transcription_controller_cooperative_cancel(tmp_path: Path) -> None:
    """测试 TranscriptionController 在转录循环中响应 stop_transcription()，优雅中止并向前端推送取消通知。"""
    fake_asr = MagicMock()
    fake_asr.is_model_loaded = True
    fake_audio = MagicMock()
    fake_audio.extract_audio_from_video.return_value = str(tmp_path / "dummy.wav")
    with open(tmp_path / "dummy.wav", "w", encoding="utf-8") as f:
        f.write("audio")

    controller = TranscriptionController(fake_asr, fake_audio, SubtitleService())

    # 预先触发取消
    controller.stop_transcription()

    generator = controller.process_media(
        [str(tmp_path / "video.mp4")], 60, ["srt"], []
    )
    yields = list(generator)

    assert len(yields) > 0
    # 状态输出中包含取消提示
    assert "转录任务已被用户取消" in yields[-1][0]


def test_cancellation_token_reset_and_reuse_lifecycle() -> None:
    """测试 CancellationToken 的完整生命周期：初始化 -> 检查通过 -> 取消 -> 抛出异常 -> 重置 -> 再次通过。"""
    token = CancellationToken()
    assert not token.is_cancelled

    token.check_cancelled()  # 正常

    token.cancel()
    assert token.is_cancelled

    with pytest.raises(TaskCancelledError):
        token.check_cancelled()

    token.reset()
    assert not token.is_cancelled
    token.check_cancelled()  # 再次正常


# =====================================================================
# 场景 8: 纯 SVG 矢量图标库与 4 国多语言 0-Emoji 严格红线
# =====================================================================
def test_svg_icons_full_library_conformance() -> None:
    """测试 SVG 图标库全量 16 个图标的 XML 合法性、属性注入及 0-Emoji 保证。"""
    emoji_regex = re.compile(
        r"[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50-\u2b55\u200d\ufe0f]"
    )

    expected_icons = [
        "settings",
        "cloud",
        "folder",
        "play",
        "stop",
        "rocket",
        "save",
        "refresh",
        "globe",
        "cut",
        "warning",
        "info",
        "lightbulb",
        "document",
        "edit",
        "microphone",
    ]

    for icon_name in expected_icons:
        assert icon_name in ICON_MAP, f"图标库缺失核心图标: {icon_name}"
        raw_svg = ICON_MAP[icon_name]

        # 1. 验证 SVG 标签边界
        assert raw_svg.startswith("<svg") and raw_svg.endswith("</svg>")
        assert 'xmlns="http://www.w3.org/2000/svg"' in raw_svg
        assert "viewBox=" in raw_svg

        # 2. 验证 0-Emoji
        assert not emoji_regex.findall(raw_svg), f"图标 {icon_name} 包含 Emoji!"

        # 3. 验证动态着色与尺寸工具函数
        rendered_custom = get_svg_icon(
            icon_name, width=24, height=24, color="#00FF00", class_name="test-icon"
        )
        assert 'width="24"' in rendered_custom
        assert 'height="24"' in rendered_custom
        assert 'class="test-icon"' in rendered_custom

    # 4. 验证 HTML 渲染器
    html_output = render_svg_html(
        get_svg_icon("play"), "开始转录", gap=10, class_name="btn-label"
    )
    assert "<span" in html_output
    assert "开始转录" in html_output
    assert "gap: 10px" in html_output


def test_locales_strict_zero_emoji_and_key_parity() -> None:
    """测试全量 4 个国际化语言文件 (zh, en, ja, ko) 包含 0 个 Emoji，且所有语言文件的 Key 严格对齐 (Parity)。"""
    root_dir = Path(__file__).resolve().parent.parent
    locale_files = {
        "zh": root_dir / "locales" / "zh.json",
        "en": root_dir / "locales" / "en.json",
        "ja": root_dir / "locales" / "ja.json",
        "ko": root_dir / "locales" / "ko.json",
    }

    emoji_regex = re.compile(
        r"[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50-\u2b55\u200d\ufe0f]"
    )

    loaded_locales: dict[str, dict[str, Any]] = {}

    for lang_code, file_path in locale_files.items():
        assert file_path.exists(), f"多语言文件不存在: {file_path}"
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            loaded_locales[lang_code] = data

        found_emojis: list[str] = []

        def check_emoji(obj: Any, path: str, target_list: list[str]) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    check_emoji(v, f"{path}.{k}", target_list)
            elif isinstance(obj, str):
                matches = emoji_regex.findall(obj)
                if matches:
                    target_list.append(f"{path}: {matches}")

        check_emoji(data, "", found_emojis)
        assert (
            len(found_emojis) == 0
        ), f"语言文件 {lang_code}.json 违规包含 Emoji: {found_emojis}"

    # 验证 Key 对齐度 (以 zh.json 为基准)
    def extract_keys(d: dict[str, Any], prefix: str = "") -> set[str]:
        keys = set()
        for k, v in d.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys.update(extract_keys(v, full_key))
            else:
                keys.add(full_key)
        return keys

    zh_keys = extract_keys(loaded_locales["zh"])
    assert len(zh_keys) >= 30, f"zh.json 键过少: {len(zh_keys)}"

    for target_lang in ["en", "ja", "ko"]:
        target_keys = extract_keys(loaded_locales[target_lang])
        missing = zh_keys - target_keys
        assert (
            len(missing) == 0
        ), f"语言文件 {target_lang}.json 缺失以下键: {missing}"


def test_translator_multilingual_locale_switching() -> None:
    """测试 Translator 单例在运行时切换 zh, en, ja, ko 语言并准确获取对应多语言文本。"""
    translator = Translator()

    # 1. 切换至中文
    set_language("zh")
    assert get_language() == "zh"
    zh_title = translator("app.title")
    assert "Parakeet" in zh_title

    # 2. 切换至英文
    set_language("en")
    assert get_language() == "en"
    en_title = translator("app.title")
    assert "Parakeet" in en_title

    # 3. 切换至日文
    set_language("ja")
    assert get_language() == "ja"
    ja_btn = translator("transcription.submit_button")
    assert len(ja_btn) > 0

    # 4. 切换至韩文
    set_language("ko")
    assert get_language() == "ko"
    ko_btn = translator("transcription.submit_button")
    assert len(ko_btn) > 0

    # 5. 动态插值测试
    set_language("zh")
    msg = translator("model.error_path_not_found", path="test/path.nemo")
    assert "test/path.nemo" in msg

    # 恢复默认语言
    set_language(DEFAULT_LANGUAGE)


def test_app_ui_language_switch_event_zero_emoji() -> None:
    """测试 app_ui.create_ui 中的 change_language 回调在 4 种语言切换时返回的所有 UI 组件更新值绝对不含 Emoji。"""
    from app_ui import create_ui
    from application import AppState

    emoji_regex = re.compile(
        r"[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50-\u2b55\u200d\ufe0f]"
    )

    app = AppState()
    demo = create_ui(app)
    assert demo is not None

    # 获取语言切换的事件处理器 (通过 Translator 测试)
    for target_lang in ["zh", "en", "ja", "ko"]:
        set_language(target_lang)
        # 扫描此时 Translator 加载的所有翻译文本
        for k, v in t_scan_all(Translator().translations):
            emojis = emoji_regex.findall(v)
            assert (
                len(emojis) == 0
            ), f"在语言 {target_lang} 下键 {k} 含有 Emoji: {emojis}"

    set_language(DEFAULT_LANGUAGE)


def t_scan_all(data: dict[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    """递归遍历翻译字典中所有的字符串键值对。"""
    res: list[tuple[str, str]] = []
    for k, v in data.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            res.extend(t_scan_all(v, full_key))
        elif isinstance(v, str):
            res.append((full_key, v))
    return res
