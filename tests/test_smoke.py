"""端到端冒烟测试（无需 GPU / NeMo / 真实 gradio）。

覆盖：全模块导入、UI 构建与事件绑定、四语言切换、
转录流水线（假 ASR → 真实字幕生成落盘）、编辑器全链路、ZIP 打包。
"""
import os
import tempfile
import zipfile

import pytest

from tests.conftest import GR_BOUND, FakeDataFrame, FakeDevice


# ---------------------------------------------------------------- fixtures
class FakeASR:
    device = FakeDevice("cpu")
    is_model_loaded = True

    def load_model_from_ngc(self, name):
        return f"云端模型 '{name}' 加载成功。"

    def load_model_from_local(self, p):
        return "本地模型加载成功。"

    def transcribe_audio_in_chunks(self, path, ms, max_chars=0, cancellation_token=None):
        return [
            {
                "start": 0.0,
                "end": 1.5,
                "segment": "hello world",
                "chars": [],
                "words": [
                    {"word": "hello", "start": 0.0, "end": 0.7},
                    {"word": "world", "start": 0.8, "end": 1.5},
                ],
            }
        ]


class FakeAudio:
    def extract_audio_from_video(self, p):
        f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        f.close()
        return f.name


class FakeTransService:
    async def translate_segments(self, *a, **k):
        return []

    async def segment_subtitles(self, *a, **k):
        return []


@pytest.fixture(scope="module")
def fake_app(tmp_path_factory):
    from controllers.model_controller import ModelController
    from controllers.subtitle_editor_controller import SubtitleEditorController
    from controllers.transcription_controller import TranscriptionController
    from controllers.translation_controller import TranslationController
    from core.subtitle_generator import SubtitleService
    from utils.config_manager import ConfigManager

    tmp = str(tmp_path_factory.mktemp("cfg"))
    cfg = ConfigManager(base_dir=tmp)
    subtitle_service = SubtitleService()

    class App:
        asr_service = FakeASR()
        config_manager = cfg
        audio_service = FakeAudio()
        subtitle_generator = subtitle_service
        model_controller = ModelController(app_services=FakeASR(), config=cfg)
        transcription_controller = TranscriptionController(FakeASR(), FakeAudio(), subtitle_service)
        subtitle_editor_controller = SubtitleEditorController(subtitle_service)
        translation_controller = TranslationController(subtitle_service, FakeTransService(), cfg)

    return App()


# ---------------------------------------------------------------- tests
def test_all_modules_importable():
    import app_ui  # noqa: F401
    import application  # noqa: F401
    import controllers.model_controller  # noqa: F401
    import controllers.subtitle_editor_controller  # noqa: F401
    import controllers.transcription_controller  # noqa: F401
    import controllers.translation_controller  # noqa: F401
    import core.asr_service  # noqa: F401
    import core.audio_processor  # noqa: F401
    import core.post_processors  # noqa: F401
    import core.subtitle_generator  # noqa: F401
    import core.translation_service  # noqa: F401
    import interfaces  # noqa: F401
    import main  # noqa: F401


def test_create_ui_builds_and_binds_once(fake_app):
    import app_ui

    GR_BOUND.clear()
    demo = app_ui.create_ui(fake_app)
    assert demo is not None
    fns = [b[0] for b in GR_BOUND if b[0] is not None]
    names = [getattr(f, "__name__", str(f)) for f in fns]
    # 回归保护：批量替换按钮历史上被重复绑定过（每次点击执行两遍）
    assert names.count("apply_batch_corrections") == 1


def test_change_language_all_locales(fake_app):
    import app_ui

    GR_BOUND.clear()
    app_ui.create_ui(fake_app)
    fns = [b[0] for b in GR_BOUND if b[0] is not None]
    change_lang = next(f for f in fns if getattr(f, "__name__", "") == "change_language")
    for lang in ["en", "ja", "ko", "zh"]:
        updates = change_lang(lang)
        assert len(updates) > 50, f"语言 {lang} 更新的组件数异常: {len(updates)}"


def test_transcription_pipeline(fake_app, tmp_path):
    tc = fake_app.transcription_controller
    media = tmp_path / "demo video.mp4"
    media.write_text("x", encoding="utf-8")

    msgs = list(tc.process_media([str(media)], 60, ["srt", "vtt", "ass"], ["word_srt"], False, 0))
    final_status, files, preview = msgs[-1]

    assert "处理完成" in final_status
    assert files is not None and len(files) == 4
    for f in files:
        assert os.path.exists(f)

    plain_srt = next(f for f in files if f.endswith("demo video.srt"))
    with open(plain_srt, "r", encoding="utf-8") as f:
        srt = f.read()
    assert "hello world" in srt
    assert "00:00:00,000 --> 00:00:01,500" in srt

    word_srt = next(f for f in files if f.endswith("_word_srt.srt"))
    with open(word_srt, "r", encoding="utf-8") as f:
        word_srt_content = f.read()
    assert word_srt_content.count("-->") == 2

    # 清理生成的字幕文件
    for f in files:
        os.remove(f)


def test_editor_roundtrip(fake_app, tmp_path):
    svc = fake_app.subtitle_generator
    ec = fake_app.subtitle_editor_controller

    srt_path = tmp_path / "sample.srt"
    srt_path.write_text(
        svc.generate_content([{"start": 0.0, "end": 1.5, "segment": "hello world"}], "srt"),
        encoding="utf-8",
    )

    class FObj:
        def __init__(self, n):
            self.name = n

    df, status = ec.load_subtitle_file([FObj(str(srt_path))])
    assert df and df[0][3] == "hello world"

    fixed = ec.apply_batch_corrections(FakeDataFrame(df), FakeDataFrame([["hello", "你好"]]))
    assert fixed[0][3] == "你好 world"

    saved = ec.save_subtitles(fixed, [FObj(str(srt_path))])
    assert saved and os.path.exists(saved)
    with open(saved, "r", encoding="utf-8") as f:
        saved_content = f.read()
    assert "你好 world" in saved_content
    os.remove(saved)


def test_zip_archive(fake_app, tmp_path):
    tc = fake_app.transcription_controller
    files = []
    for i in range(3):
        p = tmp_path / f"s{i}.srt"
        p.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n\n", encoding="utf-8")
        files.append(str(p))

    z = tc.create_zip_archive(files)
    assert z and len(zipfile.ZipFile(z).namelist()) == 3
    os.remove(z)


def test_format_time_precision(fake_app):
    svc = fake_app.subtitle_generator
    assert svc.format_time(1.001) == "00:00:01,001"  # 回归：浮点截断曾丢 1ms
    assert svc.format_time(59.9996) == "00:01:00,000"  # 进位
    assert svc.format_time(-0.5) == "00:00:00,000"  # 负值钳制


def test_parse_srt_roundtrip(fake_app):
    svc = fake_app.subtitle_generator
    segs = [
        {"start": 0.5, "end": 2.0, "segment": "line one"},
        {"start": 2.5, "end": 4.0, "segment": "多行\n字幕"},
    ]
    back = svc.parse_srt(svc.generate_content(segs, "srt"))
    assert len(back) == 2
    assert back[1]["segment"] == "多行\n字幕"
    assert abs(back[0]["start"] - 0.5) < 1e-9
