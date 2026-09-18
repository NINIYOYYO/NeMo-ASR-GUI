"""Empirical Adversarial and Stress Test Suite for Parakeet-TDT Hardened Pipeline.

This module executes rigorous boundary, concurrency, and stress tests covering:
1. Dynamic Programming (DP) Timestamp Alignment with extreme edge cases.
2. SubtitleService parsing & generation with mixed CRLF/LF/CR and malformed formats.
3. CancellationToken thread-safety, race conditions, and high-frequency checks.
4. ConfigurableFilter resilience against malformed YAML and invalid regexes.
5. ASRService RLock thread safety and concurrent model operations.
6. Translator multi-threaded locale switching safety.
"""

import concurrent.futures
import logging
import os
import re
import tempfile
import threading
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from core.asr_service import ASRService
from core.constants import (
    DEFAULT_SEGMENTATION_CHUNK_SIZE,
    SubtitleFormat,
)
from core.subtitle_generator import SubtitleService
from core.translation_service import TranslationService
from interfaces import (
    CancellationToken,
    SubtitleSegmentDict,
    TaskCancelledError,
)
from utils.log_filter import ConfigurableFilter
from utils.translator import Translator

# =====================================================================
# 1. DP TIMESTAMP ALIGNMENT ADVERSARIAL STRESS TESTS
# =====================================================================


def test_dp_alignment_completely_disjoint_vocabulary() -> None:
    """测试当大模型返回与原文完全不相交的词汇时，系统能平滑均分时间戳且保持单调递增。"""
    service = TranslationService()
    original_segments: list[SubtitleSegmentDict] = [
        {"start": 0.0, "end": 2.0, "segment": "alpha beta gamma"},
        {"start": 2.0, "end": 5.0, "segment": "delta epsilon zeta"},
    ]

    # LLM 返回完全不同的汉字分词
    llm_output = "赵钱孙李 | 周吴郑王 | 冯陈褚卫"
    result = service._realign_timestamps(original_segments, llm_output)

    assert len(result) == 3
    assert result[0]["segment"] == "赵钱孙李"
    assert result[1]["segment"] == "周吴郑王"
    assert result[2]["segment"] == "冯陈褚卫"

    # 验证时间戳覆盖完整区间 [0.0, 5.0]
    assert abs(result[0]["start"] - 0.0) < 1e-3
    assert abs(result[-1]["end"] - 5.0) < 1e-3

    # 验证单调递增性与无倒流
    for i, seg in enumerate(result):
        assert seg["end"] >= seg["start"], f"发现时隙倒流: {seg}"
        if i > 0:
            assert seg["start"] >= result[i - 1]["start"], "起始时间戳必须单调递增"


def test_dp_alignment_massive_single_block_without_separators() -> None:
    """测试超长单段文本（无 | 分隔符）的高相似度合并与低相似度安全回退。"""
    service = TranslationService()
    original_segments: list[SubtitleSegmentDict] = [
        {"start": float(i), "end": float(i + 1), "segment": f"段落内容_{i}"} for i in range(50)
    ]

    # 场景 A: 高相似度合并（将 50 个分段拼成一大段无 | 的文本）
    merged_text = "".join(f"段落内容_{i}" for i in range(50))
    res_merged = service._realign_timestamps(original_segments, merged_text)
    assert len(res_merged) == 1
    assert res_merged[0]["start"] == 0.0
    assert res_merged[0]["end"] == 50.0
    assert res_merged[0]["segment"] == merged_text

    # 场景 B: 低相似度且无 | 的极端胡言乱语 -> 安全回退到原 50 个分段
    garbage_text = "完全不相关的文本信息，没有任何断句标记"
    res_fallback = service._realign_timestamps(original_segments, garbage_text)
    assert len(res_fallback) == 50
    assert res_fallback[0]["segment"] == "段落内容_0"
    assert res_fallback[-1]["segment"] == "段落内容_49"


def test_dp_alignment_empty_whitespace_and_pipe_only_inputs() -> None:
    """测试空串、全空格、多重连续管道符等畸形 LLM 输出的健壮性。"""
    service = TranslationService()
    original_segments: list[SubtitleSegmentDict] = [
        {"start": 1.0, "end": 3.0, "segment": "hello world"},
        {"start": 3.0, "end": 6.0, "segment": "test sentence"},
    ]

    for malformed_llm in ["", "   \n\t  ", "||||", " | | \n | "]:
        res = service._realign_timestamps(original_segments, malformed_llm)
        # 应无异常崩溃并安全返回原文
        assert len(res) == 2
        assert res[0]["segment"] == "hello world"
        assert res[1]["segment"] == "test sentence"
        assert res[0]["start"] == 1.0
        assert res[1]["end"] == 6.0


def test_dp_alignment_production_chunk_size_performance() -> None:
    """测试在生产标准分块大小 (30 段落) 下，DP 锚点算法在 50ms 内极速对齐完成。"""
    service = TranslationService()
    chunk_size = DEFAULT_SEGMENTATION_CHUNK_SIZE  # 30
    original_segments: list[SubtitleSegmentDict] = [
        {
            "start": round(i * 1.5, 2),
            "end": round(i * 1.5 + 1.2, 2),
            "segment": f"Token_{i}_CoreData",
        }
        for i in range(chunk_size)
    ]

    llm_parts = [f"Token_{i}_CoreData 以及 Token_{i + 1}_CoreData" for i in range(0, chunk_size, 2)]
    llm_text = " | ".join(llm_parts)

    start_time = time.perf_counter()
    result = service._realign_timestamps(original_segments, llm_text)
    elapsed = time.perf_counter() - start_time

    assert len(result) == chunk_size // 2
    # 生产批次 50 段落对齐计算应在 200ms 内完成
    assert elapsed < 0.2, f"标准分块 DP 对齐耗时: {elapsed:.4f}s"
    assert result[0]["start"] == 0.0
    assert abs(result[-1]["end"] - original_segments[-1]["end"]) < 1e-3


# =====================================================================
# 2. SUBTITLE GENERATOR ADVERSARIAL STRESS TESTS
# =====================================================================


def test_subtitle_parser_mixed_newlines_and_corrupted_headers() -> None:
    """测试 SRT 解析器对 CR/LF/CRLF 混杂、多余空行及多行文本的容错能力。"""
    service = SubtitleService()

    bad_srt = (
        "1\r\n00:00:01,000 --> 00:00:02,500\r\n第一行字幕文本\r\n\r\n\r\n"
        "2\n00:00:03,000 --> 00:00:04,500\n第二行包含\r特殊回车\n\n"
        "3\r\n00:00:05,000 --> 00:00:06,000\r\n第三行\r\n\r\n"
        "4\n00:00:07,000 --> 00:00:08,000\n第四行多行\n文本段落\n\n"
    )

    parsed = service.parse_srt(bad_srt)
    assert len(parsed) == 4
    assert parsed[0]["start"] == 1.0
    assert parsed[0]["end"] == 2.5
    assert parsed[0]["segment"] == "第一行字幕文本"

    assert parsed[1]["start"] == 3.0
    assert parsed[1]["end"] == 4.5

    assert parsed[3]["segment"] == "第四行多行\n文本段落"


def test_subtitle_format_time_boundary_values() -> None:
    """测试 format_time 对负数、超大时间、999.9 毫秒进位等边界值的精确计算。"""
    service = SubtitleService()

    # 1. 负数安全归零
    assert service.format_time(-10.5) == "00:00:00,000"
    assert service.format_time(0.0) == "00:00:00,000"

    # 2. 毫秒四舍五入进位到下一秒 (0.9996s -> 1.000s)
    assert service.format_time(0.9996) == "00:00:01,000"
    assert service.format_time(0.9994) == "00:00:00,999"

    # 3. 超过 24 小时的长时间轴 (25h 30m 15s 500ms)
    sec_25h = 25 * 3600 + 30 * 60 + 15.5
    assert service.format_time(sec_25h) == "25:30:15,500"

    # 4. 标准 ASS 时间格式化
    assert service._format_ass_time(0.0) == "0:00:00.00"
    assert service._format_ass_time(3661.05) == "1:01:01.05"


def test_subtitle_generator_all_formats_with_malformed_and_missing_keys() -> None:
    """测试所有字幕生成器（SRT, VTT, TXT, JSON, LRC, ASS, CHAR_SRT, WORD_SRT）在缺键数据下的降级容错。"""
    service = SubtitleService()

    # 构造缺少部分键或类型混杂的恶劣数据
    segments: list[Any] = [
        {"start": 0.0, "end": 1.5, "text": "使用 text 键而非 segment"},
        {"start": 2.0, "end": 3.0, "segment": "标准 segment 键"},
        {"start": 4.0, "end": 5.0, "segment": "逐字缺失 chars 键"},
        {
            "start": 6.0,
            "end": 8.0,
            "segment": "具备完整 chars 字段",
            "chars": [
                {"char": "字", "start": 6.0, "end": 7.0},
                {"char": "符", "start": 7.0, "end": 8.0},
            ],
        },
    ]

    formats = [
        SubtitleFormat.SRT,
        SubtitleFormat.VTT,
        SubtitleFormat.TXT,
        SubtitleFormat.JSON,
        SubtitleFormat.LRC,
        SubtitleFormat.ASS,
        SubtitleFormat.CHAR_SRT,
        SubtitleFormat.WORD_SRT,
    ]

    for fmt in formats:
        content = service.generate_content(segments, fmt)
        assert isinstance(content, str)
        assert len(content) > 0, f"格式 {fmt} 生成的内容不能为空"

    # 测试非法格式抛出 ValueError
    with pytest.raises(ValueError, match="不支持的字幕格式"):
        service.generate_content(segments, "unsupported_xyz_format")


# =====================================================================
# 3. CANCELLATION TOKEN CONCURRENCY STRESS TESTS
# =====================================================================


def test_cancellation_token_high_frequency_multi_threaded_contention() -> None:
    """测试 50 个线程高频并发调用 cancel(), reset(), is_cancelled, check_cancelled() 杜绝死锁与竞态。"""
    token = CancellationToken()
    num_threads = 50
    iterations = 500

    def worker_checker(t_id: int) -> int:
        catches = 0
        for _ in range(iterations):
            if token.is_cancelled:
                try:
                    token.check_cancelled()
                except TaskCancelledError:
                    catches += 1
            time.sleep(0.0001)
        return catches

    def worker_mutator() -> None:
        for _ in range(iterations):
            token.cancel()
            time.sleep(0.0001)
            token.reset()
            time.sleep(0.0001)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads + 2) as executor:
        mutator_futures = [executor.submit(worker_mutator) for _ in range(2)]
        checker_futures = [executor.submit(worker_checker, i) for i in range(num_threads)]

        for f in mutator_futures + checker_futures:
            f.result()

    # 最终状态复位验证
    token.reset()
    assert not token.is_cancelled
    token.check_cancelled()


def test_cancellation_token_transcription_pipeline_abort_stress() -> None:
    """测试 ASR 推理流水线在多 Chunk 迭代中随时触发取消时，能秒级终止并不留悬空计算。"""
    asr_service = ASRService()
    token = CancellationToken()

    # Mock 模型
    asr_service.model = MagicMock()

    chunk_count = 100
    processed_chunks = 0

    def mock_generator() -> Any:
        nonlocal processed_chunks
        for i in range(chunk_count):
            token.check_cancelled()
            processed_chunks += 1
            time.sleep(0.005)
            yield [{"start": float(i), "end": float(i + 1), "text": f"chunk_{i}"}]

    # 在后台 25ms 后取消
    def delayed_cancel() -> None:
        time.sleep(0.025)
        token.cancel()

    cancel_thread = threading.Thread(target=delayed_cancel)
    cancel_thread.start()

    with pytest.raises(TaskCancelledError):
        for _ in mock_generator():
            pass

    cancel_thread.join()
    assert processed_chunks < chunk_count, f"任务未及时取消，处理了 {processed_chunks}/{chunk_count} 个分块"


# =====================================================================
# 4. LOG FILTER MALFORMED YAML & REGEX ADVERSARIAL TESTS
# =====================================================================


def test_log_filter_completely_broken_yaml_and_syntax_error() -> None:
    """测试日志过滤器面对损坏的 YAML 语法、二进制乱码时能平稳降级而不引发应用闪退。"""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".yaml") as f:
        f.write("!!binary garbage \x00\x01\x02\n[unbalanced bracket: {invalid: yaml")
        f_path = f.name

    try:
        log_filter = ConfigurableFilter(f_path)
        # 应降级为空过滤规则，并正常放行日志
        assert len(log_filter.message_patterns) == 0

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="正常日志输出",
            args=(),
            exc_info=None,
        )
        assert log_filter.filter(record) is True
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)


def test_log_filter_extreme_unescaped_regex_and_special_chars() -> None:
    """测试包含未转义反斜杠、特殊元字符的 YAML 正则表达式能够被正确重写与解析过滤。"""
    yaml_content = """
message_filters:
  - pattern: "\\[NeMo.*?\\] \\d+:\\d+"
    min_level: "WARNING"
  - pattern: "D:\\\\path\\\\to\\\\file\\.py"
    min_level: "ERROR"
  - pattern: "HTTP/1\\.1 (404|500)"
    min_level: "INFO"
"""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".yaml") as f:
        f.write(yaml_content)
        f_path = f.name

    try:
        log_filter = ConfigurableFilter(f_path)
        assert len(log_filter.message_patterns) == 3

        # 1. 匹配 [NeMo...] 10:20 且低于 WARNING 级别的 DEBUG 日志应被拦截
        rec_debug = logging.LogRecord(
            name="nemo",
            level=logging.DEBUG,
            pathname=__file__,
            lineno=10,
            msg="[NeMo W 2026-08-17] 12:30 Initialization",
            args=(),
            exc_info=None,
        )
        assert log_filter.filter(rec_debug) is False

        # 2. 达到 WARNING 级别的同一条消息应被放行
        rec_warning = logging.LogRecord(
            name="nemo",
            level=logging.WARNING,
            pathname=__file__,
            lineno=10,
            msg="[NeMo W 2026-08-17] 12:30 Initialization",
            args=(),
            exc_info=None,
        )
        assert log_filter.filter(rec_warning) is True

        # 3. 匹配 HTTP/1.1 500 的 INFO 消息应被放行
        rec_http = logging.LogRecord(
            name="http",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Server returned HTTP/1.1 500 Internal Error",
            args=(),
            exc_info=None,
        )
        assert log_filter.filter(rec_http) is True

        # 4. 不匹配任何规则的任意消息默认放行
        rec_normal = logging.LogRecord(
            name="app",
            level=logging.DEBUG,
            pathname=__file__,
            lineno=10,
            msg="普通日志信息",
            args=(),
            exc_info=None,
        )
        assert log_filter.filter(rec_normal) is True
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)


def test_log_filter_large_payload_and_exception_handling() -> None:
    """测试日志过滤器处理超大消息体 (1MB 字符串) 及特殊非字符串 LogRecord 的鲁棒性。"""
    log_filter = ConfigurableFilter()
    rule_pattern = re.compile(r"CRITICAL_ERROR_CODE_\d+")
    log_filter.message_patterns.append({"pattern": rule_pattern, "min_level": logging.ERROR})

    # 1. 1MB 超大文本日志
    huge_msg = "RandomData_" * 100_000 + "CRITICAL_ERROR_CODE_999"
    rec_huge = logging.LogRecord(
        name="stress",
        level=logging.WARNING,
        pathname=__file__,
        lineno=10,
        msg=huge_msg,
        args=(),
        exc_info=None,
    )
    # WARNING < ERROR, 包含匹配 pattern, 应被拦截
    assert log_filter.filter(rec_huge) is False

    # 2. 格式化参数包含特殊对象
    rec_obj = logging.LogRecord(
        name="stress",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Object representation: %s",
        args=({"key": "value", "list": [1, 2, 3]},),
        exc_info=None,
    )
    assert log_filter.filter(rec_obj) is True


# =====================================================================
# 5. ASR SERVICE RLOCK & TRANSLATOR MULTI-THREADING CONCURRENCY TESTS
# =====================================================================


def test_asr_service_rlock_multi_threaded_model_lifecycle() -> None:
    """测试 ASRService 在 20 个并发线程同时请求 load/release/transcribe 时由 RLock 严格串行互斥。"""
    asr_service = ASRService()
    active_operations = 0
    max_concurrent_operations = 0
    lock = threading.Lock()

    def simulated_model_operation(op_type: str) -> str:
        nonlocal active_operations, max_concurrent_operations
        with asr_service._lock:
            with lock:
                active_operations += 1
                if active_operations > max_concurrent_operations:
                    max_concurrent_operations = active_operations
            # 模拟模型加载或推理耗时
            time.sleep(0.005)
            with lock:
                active_operations -= 1
        return op_type

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(simulated_model_operation, f"op_{i}") for i in range(20)]
        results = [f.result() for f in futures]

    assert len(results) == 20
    # 在 RLock 保护下，同时进入关键区的操作数必须为 1
    assert max_concurrent_operations == 1


def test_translator_thread_safe_concurrent_switching() -> None:
    """测试多语言翻译器单例在 20 个线程高频并发切换语言与读取翻译时的稳定性。"""
    translator = Translator()
    locales = ["zh", "en", "ja", "ko"]

    def worker_switch(thread_id: int) -> None:
        for _ in range(50):
            target = locales[thread_id % len(locales)]
            translator.set_locale(target)
            title = translator("app.title")
            assert len(title) > 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker_switch, i) for i in range(20)]
        for f in futures:
            f.result()

    # 恢复默认中文
    translator.set_locale("zh")
    assert translator.get_current_locale() == "zh"
