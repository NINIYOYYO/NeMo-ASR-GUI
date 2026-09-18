"""Milestone M2 流水线加固与性能重构专项单元测试。

测试矩阵：
1. Windows CRLF 与 Unix LF SRT 换行解析、生成格式化及大列表性能。
2. ASR 内存张量 (In-Memory Tensor) 直传推理与磁盘临时文件降级回退。
3. 动态规划 (DP) / 锚点词时间戳重对齐算法抗词句增删改漂移能力。
4. Google Gemini API Key HTTP Header (x-goog-api-key) 传输安全性。
5. 协作式 CancellationToken 取消机制在 ASRService 与 Controller 中的响应。
6. TranslationController 异步非阻塞 (asyncio.to_thread) 文件 I/O。
"""

import os
from typing import Any
from unittest.mock import MagicMock

import pytest
import torch
from pydub.generators import Sine

from controllers.transcription_controller import TranscriptionController
from controllers.translation_controller import TranslationController
from core.asr_service import ASRService
from core.subtitle_generator import SubtitleService
from core.translation_service import TranslationService
from interfaces import CancellationToken, TaskCancelledError
from utils.config_manager import ConfigManager


# =====================================================================
# 1. Windows CRLF & Unix LF SRT Parsing & Generation Tests
# =====================================================================
def test_srt_crlf_and_lf_parsing_and_formatting():
    """测试 Windows CRLF (\\r\\n) 与 Unix LF (\\n) 换行在 SRT 解析中的完全兼容性与生成一致性。"""
    service = SubtitleService()

    # 1.1 Unix LF SRT
    lf_srt = "1\n00:00:01,000 --> 00:00:03,500\nHello Unix World\n\n2\n00:00:04,000 --> 00:00:06,250\nLine 2 Text\n\n"
    lf_segments = service.parse_srt(lf_srt)
    assert len(lf_segments) == 2
    assert lf_segments[0]["segment"] == "Hello Unix World"
    assert lf_segments[0]["start"] == 1.0
    assert lf_segments[0]["end"] == 3.5
    assert lf_segments[1]["segment"] == "Line 2 Text"
    assert lf_segments[1]["start"] == 4.0
    assert lf_segments[1]["end"] == 6.25

    # 1.2 Windows CRLF SRT
    crlf_srt = (
        "1\r\n"
        "00:00:01,000 --> 00:00:03,500\r\n"
        "Hello Windows World\r\n\r\n"
        "2\r\n"
        "00:00:04,000 --> 00:00:06,250\r\n"
        "Line 2 CRLF Text\r\n\r\n"
    )
    crlf_segments = service.parse_srt(crlf_srt)
    assert len(crlf_segments) == 2
    assert crlf_segments[0]["segment"] == "Hello Windows World"
    assert crlf_segments[0]["start"] == 1.0
    assert crlf_segments[0]["end"] == 3.5
    assert crlf_segments[1]["segment"] == "Line 2 CRLF Text"
    assert crlf_segments[1]["start"] == 4.0
    assert crlf_segments[1]["end"] == 6.25

    # 1.3 混合换行符与多行字幕内容
    mixed_srt = (
        "1\r\n"
        "00:00:00,500 --> 00:00:02,000\n"
        "第一行字幕\r\n第二行字幕\n\n"
        "2\n"
        "00:00:03,000 --> 00:00:05,000\r\n"
        "第三行字幕\r\n\r\n"
    )
    mixed_segments = service.parse_srt(mixed_srt)
    assert len(mixed_segments) == 2
    assert "第一行字幕\n第二行字幕" in mixed_segments[0]["segment"].replace("\r\n", "\n")

    # 1.4 空文本容错
    assert service.parse_srt("") == []
    assert service.parse_srt("   \r\n\n  ") == []

    # 1.5 所有输出格式列表累积生成验证
    sample_segments = [
        {
            "start": 0.0,
            "end": 2.0,
            "segment": "Hello World",
            "words": [
                {"word": "Hello", "start": 0.0, "end": 0.8},
                {"word": "World", "start": 1.0, "end": 2.0},
            ],
            "chars": [
                {"char": "H", "start": 0.0, "end": 0.2},
                {"char": "e", "start": 0.2, "end": 0.4},
            ],
        },
        {"start": 2.5, "end": 4.5, "segment": "Second Sentence"},
    ]

    for fmt in ["srt", "vtt", "txt", "json", "lrc", "word_srt", "char_srt", "ass"]:
        output = service.generate_content(sample_segments, fmt)
        assert isinstance(output, str)
        assert len(output) > 0

    with pytest.raises(ValueError, match="不支持的字幕格式"):
        service.generate_content(sample_segments, "unsupported_format")


# =====================================================================
# 2. In-Memory Tensor Inference & Fallback Tests
# =====================================================================
def test_in_memory_tensor_inference_path(tmp_path):
    """测试 ASRService 优先使用内存 Tensor 直传推理，且在不支持时平滑降级为临时磁盘 WAV 文件。"""
    # 2.1 创建 2 秒测试 WAV 音频
    sine_wave = Sine(440).to_audio_segment(duration=2000)
    sine_wave = sine_wave.set_frame_rate(16000).set_channels(1)
    wav_path = str(tmp_path / "test_audio.wav")
    sine_wave.export(wav_path, format="wav")

    asr = ASRService()

    # 2.2 测试内存张量直传成功路径
    class MockTensorModel:
        def __init__(self):
            self.calls: list[dict[str, Any]] = []

        def transcribe(self, paths2audio_files=None, audio=None, **kwargs):
            self.calls.append({"paths": paths2audio_files, "audio": audio, "kwargs": kwargs})
            mock_hyp = MagicMock()
            mock_hyp.text = "tensor transcribed text"
            mock_hyp.timestamp = {"segment": [{"start": 0.0, "end": 1.0, "segment": "tensor transcribed text"}]}
            mock_hyp.words = []
            return [mock_hyp]

    tensor_model = MockTensorModel()
    asr.model = tensor_model

    results = asr.transcribe_audio_in_chunks(wav_path, chunk_length_ms=1000)
    assert len(results) > 0
    # 验证确实调用了 audio 内存入参，且没有传入磁盘文件路径
    assert len(tensor_model.calls) > 0
    assert tensor_model.calls[0]["audio"] is not None
    assert isinstance(tensor_model.calls[0]["audio"][0], torch.Tensor)
    assert tensor_model.calls[0]["paths"] is None

    # 2.3 测试模型不支持 audio 参数时的降级回退路径
    class MockDiskOnlyModel:
        def __init__(self):
            self.calls: list[dict[str, Any]] = []

        def transcribe(self, paths2audio_files=None, **kwargs):
            if "audio" in kwargs:
                raise TypeError("MockDiskOnlyModel.transcribe() got an unexpected keyword argument 'audio'")
            self.calls.append({"paths": paths2audio_files, "kwargs": kwargs})
            mock_hyp = MagicMock()
            mock_hyp.text = "disk fallback text"
            mock_hyp.timestamp = {"segment": [{"start": 0.0, "end": 1.0, "segment": "disk fallback text"}]}
            mock_hyp.words = []
            return [mock_hyp]

    disk_model = MockDiskOnlyModel()
    asr.model = disk_model

    fallback_results = asr.transcribe_audio_in_chunks(wav_path, chunk_length_ms=1000)
    assert len(fallback_results) > 0
    assert len(disk_model.calls) > 0
    assert disk_model.calls[0]["paths"] is not None
    assert os.path.exists(wav_path)  # 原音频未被误删


# =====================================================================
# 3. DP / Anchor-Word Timestamp Alignment Tests
# =====================================================================
def test_dp_anchor_timestamp_alignment_resilience():
    """测试基于动态规划 (DP) 与锚点词序列对齐算法在 LLM 增删改文本时的抗累积漂移能力。"""
    service = TranslationService()

    # 原音频转录段落（包含 3 句话，总长 6 秒）
    original_segments = [
        {"start": 0.0, "end": 2.0, "segment": "人工智能与深度学习"},
        {"start": 2.0, "end": 4.0, "segment": "正在彻底改变计算机视觉"},
        {"start": 4.0, "end": 6.0, "segment": "以及自然语言处理领域"},
    ]

    # 场景 1: LLM 仅插入断句标记 '|'，无任何字词修改
    llm_clean = "人工智能与深度学习 | 正在彻底改变计算机视觉 | 以及自然语言处理领域"
    aligned_1 = service.align_timestamps(original_segments, llm_clean)
    assert len(aligned_1) == 3
    assert aligned_1[0]["segment"] == "人工智能与深度学习"
    assert abs(aligned_1[0]["start"] - 0.0) < 0.05
    assert abs(aligned_1[1]["start"] - 2.0) < 0.05
    assert abs(aligned_1[2]["start"] - 4.0) < 0.05

    # 场景 2: LLM 在第一句中添加了 10 个修饰字词，但第二句与第三句保持不变
    # 传统字符计数法会导致第二句起始时间严重向后漂移 ~1-2 秒
    # DP 锚点对齐法应精准识别第二句的锚点词，将其锚定在 ~2.0s
    llm_with_added_words = (
        "最新研发的高精度通用人工智能与深度学习核心算法 | 正在彻底改变计算机视觉 | 以及自然语言处理领域"
    )
    aligned_2 = service.align_timestamps(original_segments, llm_with_added_words)
    assert len(aligned_2) == 3
    assert "人工智能与深度学习" in aligned_2[0]["segment"]
    # 第二句锚点依然稳固在 2.0 秒附近（误差 < 0.2s），无累积漂移
    assert abs(aligned_2[1]["start"] - 2.0) < 0.25
    # 第三句锚点依然稳固在 4.0 秒附近
    assert abs(aligned_2[2]["start"] - 4.0) < 0.25

    # 场景 3: LLM 在第一句中删除了部分词，并修改了标点
    llm_with_deleted_words = "AI深度学习 | 彻底改变计算机视觉 | 以及自然语言处理"
    aligned_3 = service.align_timestamps(original_segments, llm_with_deleted_words)
    assert len(aligned_3) == 3
    # 验证单调性与非负时长
    for seg in aligned_3:
        assert seg["end"] > seg["start"]
        assert seg["end"] - seg["start"] >= 0.05

    # 场景 4: 极端情况 — LLM 彻底改写文本（0 匹配），平滑均分
    llm_completely_rewritten = "Alpha | Beta | Gamma | Delta"
    aligned_4 = service.align_timestamps(original_segments, llm_completely_rewritten)
    assert len(aligned_4) == 4
    assert aligned_4[0]["start"] == 0.0
    for i in range(len(aligned_4) - 1):
        assert aligned_4[i + 1]["start"] >= aligned_4[i]["start"]
        assert aligned_4[i]["end"] > aligned_4[i]["start"]

    # 场景 5: 空输入与无断句标记容错
    assert service.align_timestamps([], "test") == []
    assert service.align_timestamps(original_segments, "") == original_segments
    assert service.align_timestamps(original_segments, "没有断句标记的文本") == original_segments


# =====================================================================
# 4. Google Gemini API Key HTTP Header Security Tests
# =====================================================================
@pytest.mark.asyncio
async def test_gemini_api_key_passed_in_header_not_query_url():
    """测试调用 Gemini API 时，API Key 必须通过 HTTP Header 'x-goog-api-key' 传输，严禁在 URL Query 中拼接。"""
    import respx
    from httpx import Response

    service = TranslationService()

    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        ).mock(
            return_value=Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": '{"0": "你好世界"}'}]}}]},
            )
        )

        res = await service._call_llm_async(
            prompt="test prompt",
            api_key="AIzaSySecRetKey123456",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-1.5-flash",
            is_json=True,
        )

        assert res == '{"0": "你好世界"}'
        assert route.called
        call_request = route.calls.last.request
        # 验证 1: URL Query 中绝对不含 'key=' 或 API Key 字符串
        assert "key=" not in str(call_request.url)
        assert "?key=" not in str(call_request.url)
        assert "AIzaSySecRetKey123456" not in str(call_request.url)

        # 验证 2: API Key 必须位于 HTTP Header 'x-goog-api-key' 中
        assert call_request.headers.get("x-goog-api-key") == "AIzaSySecRetKey123456"


# =====================================================================
# 5. Cooperative CancellationToken Tests
# =====================================================================
def test_cancellation_token_logic():
    """测试 CancellationToken 的状态机、协作式中断与重置。"""
    token = CancellationToken()
    assert not token.is_cancelled

    token.check_cancelled()  # 未取消时正常通过

    token.cancel()
    assert token.is_cancelled

    with pytest.raises(TaskCancelledError, match="任务已被用户取消"):
        token.check_cancelled()

    token.reset()
    assert not token.is_cancelled
    token.check_cancelled()


def test_asr_service_cancellation_interruption(tmp_path):
    """测试 ASRService 分块转录在接收到 CancellationToken 取消信号时立即终止后续分块。"""
    # 创建 5 秒的音频
    sine_wave = Sine(440).to_audio_segment(duration=5000)
    sine_wave = sine_wave.set_frame_rate(16000).set_channels(1)
    wav_path = str(tmp_path / "long_audio.wav")
    sine_wave.export(wav_path, format="wav")

    asr = ASRService()
    processed_chunks = []

    class MockLongModel:
        def transcribe(self, audio=None, **kwargs):
            processed_chunks.append(len(processed_chunks) + 1)
            mock_hyp = MagicMock()
            mock_hyp.text = f"chunk {len(processed_chunks)}"
            mock_hyp.timestep = None
            mock_hyp.words = []
            return [mock_hyp]

    asr.model = MockLongModel()

    token = CancellationToken()

    # 在处理第 1 个 chunk 后设置取消
    token.cancel()

    results = asr.transcribe_audio_in_chunks(wav_path, chunk_length_ms=1000, cancellation_token=token)
    # 因为循环一开始就检测到 cancelled，因此处理 0 个 chunk
    assert len(results) == 0
    assert len(processed_chunks) == 0


def test_transcription_controller_cancellation_integration(tmp_path):
    """测试 TranscriptionController 在取消令牌触发后向前端推送取消状态并退出。"""
    fake_asr = MagicMock()
    fake_asr.is_model_loaded = True
    fake_asr.transcribe_audio_in_chunks.return_value = [{"start": 0.0, "end": 1.0, "segment": "hi"}]

    fake_audio = MagicMock()
    fake_audio.extract_audio_from_video.return_value = str(tmp_path / "dummy.wav")
    with open(tmp_path / "dummy.wav", "w", encoding="utf-8") as f:
        f.write("dummy audio")

    controller = TranscriptionController(fake_asr, fake_audio, SubtitleService())

    # 预先触发取消
    controller.stop_transcription()
    assert controller.cancellation_token.is_cancelled

    # 执行 process_media，在开始处理前即退出
    generator = controller.process_media([str(tmp_path / "test.mp4")], 60, ["srt"], [])
    messages = list(generator)
    assert len(messages) > 0
    # 状态提示包含取消信息
    assert "转录任务已被用户取消" in messages[-1][0]


# =====================================================================
# 6. Asyncio.to_thread File I/O Tests
# =====================================================================
@pytest.mark.asyncio
async def test_translation_controller_async_file_io(tmp_path):
    """测试 TranslationController.handle_translation 与 handle_ai_segmentation 正确使用 asyncio.to_thread 读写文件。"""
    subtitle_service = SubtitleService()
    fake_translation_service = MagicMock()

    async def fake_translate(segments, *args, **kwargs):
        return [{"start": 0.0, "end": 1.0, "segment": "你好世界"}]

    async def fake_segment(segments, *args, **kwargs):
        return [{"start": 0.0, "end": 1.0, "segment": "智能断句"}]

    fake_translation_service.translate_segments = fake_translate
    fake_translation_service.segment_subtitles = fake_segment

    cfg = ConfigManager(base_dir=str(tmp_path))
    controller = TranslationController(subtitle_service, fake_translation_service, cfg)
    controller.output_dir = tmp_path / "translated"
    controller.output_dir.mkdir(parents=True, exist_ok=True)

    # 写入测试字幕文件
    input_srt = tmp_path / "input.srt"
    with open(input_srt, "w", encoding="utf-8") as f:
        f.write("1\n00:00:00,000 --> 00:00:01,000\nHello World\n\n")

    class FileObj:
        def __init__(self, name):
            self.name = name

    # 6.1 翻译异步执行
    status, files, preview = await controller.handle_translation(
        [FileObj(str(input_srt))],
        target_lang="Chinese",
        is_bilingual=False,
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o",
    )
    assert "成功翻译" in status
    assert files is not None and len(files) == 1
    assert os.path.exists(files[0])
    with open(files[0], "r", encoding="utf-8") as f:
        content = f.read()
    assert "你好世界" in content

    # 6.2 断句异步执行
    seg_status, seg_files = await controller.handle_ai_segmentation(
        [FileObj(str(input_srt))],
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o",
    )
    assert "成功处理" in seg_status
    assert seg_files is not None and len(seg_files) == 1
    assert os.path.exists(seg_files[0])
    with open(seg_files[0], "r", encoding="utf-8") as f:
        seg_content = f.read()
    assert "智能断句" in seg_content
