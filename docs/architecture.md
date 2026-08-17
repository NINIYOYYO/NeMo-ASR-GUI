# 架构说明

本文档描述 Parakeet-TDT-GUI 的分层结构、模块职责、关键数据结构与主要数据流，帮助贡献者快速定位代码。

## 分层总览

```
┌─────────────────────────────────────────────────────┐
│  app_ui.py            Gradio 界面（布局 + 事件绑定） │
├─────────────────────────────────────────────────────┤
│  controllers/         控制器：UI 事件 → 参数整理 →   │
│                       调用服务 → 返回 UI 可用结果    │
├─────────────────────────────────────────────────────┤
│  core/                核心服务：ASR 推理、音频处理、 │
│                       字幕生成/解析、LLM 翻译断句    │
├─────────────────────────────────────────────────────┤
│  utils/               横切能力：日志、配置、i18n、   │
│                       异常定义                       │
└─────────────────────────────────────────────────────┘
          ▲ 所有跨层调用面向 interfaces.py 中的抽象接口
```

组装根（composition root）在 `main.py`：`create_app()` 创建全部服务并注入 `Application`（`application.py`），后者再构造各控制器并交给 `create_ui()` 绑定到界面。

## 模块职责

| 模块 | 职责 | 关键点 |
|------|------|--------|
| `main.py` | 启动入口、依赖组装 | 唯一允许直接 new 具体服务的地方 |
| `application.py` | 持有服务与控制器，暴露只读属性 | 实现 `IApplication` |
| `app_ui.py` | Gradio 布局、事件绑定、语言切换 | 不含业务逻辑；`change_language` 只保存 `language` 配置 |
| `controllers/model_controller.py` | 加载云端/本地模型，保存模型配置 | 配置键为 `chunk_length_s` |
| `controllers/transcription_controller.py` | 批量转录编排：提取音频 → 分块转录 → 生成多格式字幕 → 落盘 | 生成器函数，逐步 yield 状态；单文件失败跳过不中断队列；汇总在循环外 |
| `controllers/subtitle_editor_controller.py` | 字幕加载/批量替换/保存、校对本持久化 | 只调用 `ISubtitleGenerator` 公开 API |
| `controllers/translation_controller.py` | 翻译与断句的文件级编排 | async，输出至 `subtitles/translated/` |
| `core/asr_service.py` | NeMo 模型生命周期 + 分块推理 | 加载失败返回错误字符串（不抛异常，避免启动崩溃）；切换模型前释放显存 |
| `core/audio_processor.py` | FFmpeg 提取 16kHz 单声道 WAV | 启动时检测 ffmpeg 可用性 |
| `core/post_processors.py` | 转录后处理**策略模式** | 见下文"扩展点" |
| `core/subtitle_generator.py` | 6+2 种字幕格式生成、SRT 解析 | 公开 `format_time` / `srt_time_to_seconds`；毫秒整体四舍五入 |
| `core/translation_service.py` | LLM 调用（OpenAI 兼容 + Gemini 原生）、并发调度、重试 | ID-Mapping 防错位；429 退避 20s；彻底失败回退原文保全时间轴 |
| `utils/` | 非阻塞日志（QueueListener）、配置管理、i18n 单例 | `save_config` 忽略未知键并打警告 |

## 核心数据结构：segment 字典

全链路以"段落字典"为通用货币（后续演进方向是升级为 `dataclass`）：

```python
{
    "start": float,      # 全局起始秒
    "end": float,        # 全局结束秒
    "segment": str,      # 文本
    "chars": [ {"char": str, "start": float, "end": float}, ... ],  # 可选
    "words": [ {"word": str, "start": float, "end": float}, ... ],  # 可选
}
```

`chars` / `words` 供逐字/逐词格式（`char_srt` / `word_srt`）使用；缺失时这两种格式回退为段落级输出。

## 主要数据流

### 转录

```
用户上传媒体文件
  → TranscriptionController.process_media          (yield 状态给 UI)
    → AudioService.extract_audio_from_video        (ffmpeg → 16kHz mono WAV)
    → ASRService.transcribe_audio_in_chunks
        按 chunk_length_s 切块 → 每块 NeMo transcribe(timestamps=True)
        → processor_strategy.process(...)          (局部时间 + 块偏移 → 全局时间)
    → SubtitleService.generate_content(fmt)        (每种勾选格式一次)
  → 写入 subtitles/ → 返回文件列表 + 预览
```

### 翻译 / 断句

```
SRT 文件 → SubtitleService.parse_srt → segments
  → TranslationService.translate_segments / segment_subtitles
      chunk_size 分块 → asyncio.Semaphore(concurrency) 并发
      → _process_chunk_with_retry (最多 3 次，429 特殊退避)
          翻译：ID-Map JSON 映射，按 ID 取回，缺失回退原文
          断句：纯文本插 '|' → _realign_timestamps 按字符比例重排时间轴
  → SubtitleService.generate_content("srt") → subtitles/translated/
```

## 扩展点

### 1. 新增转录后处理策略（不同语言/模型的断句逻辑）

在 `core/post_processors.py` 实现 `ITranscriptionStrategy.process()`，然后在 `ASRService._update_strategy()` 中按模型名注册。现有实现：

- `DefaultSegmentStrategy`：使用模型自带 segment 级时间戳，支持超长句按比例拆分
- `JapaneseCharStrategy`：丢弃 segment，从 char 级时间戳按标点/静音/长度重组句子

### 2. 新增字幕导出格式

在 `SubtitleService` 中新增 `_generate_<格式名>` 方法即可——`generate_content` 通过反射分发，UI 的格式勾选框加上同名选项即完成接入。逐词/逐字类格式还需在 `TranscriptionController.FORMAT_SPECS` 登记文件名后缀。

### 3. 新增 LLM 接口适配

`TranslationService._call_llm_async` 目前按 base_url 区分 OpenAI 兼容与 Gemini 原生两条路径；新增协议时在此处分支并保持"输入 prompt → 返回纯文本"的契约。

## 测试策略

`tests/conftest.py` 在导入业务代码前为缺失的重依赖（gradio/torch/nemo/pydub/openai/httpx/pandas/yaml）注入轻量桩，因此核心逻辑测试**不需要 GPU、NeMo 或完整依赖**，CI 可直接运行。`tests/test_smoke.py` 覆盖：全模块导入、UI 构建与事件绑定（含"批量替换只绑定一次"回归）、四语言切换、假 ASR → 真实字幕落盘的完整流水线、编辑器全链路、ZIP 打包与时间戳精度。

## 已知设计债（按优先级）

1. ASR 模型无并发保护：转录进行中切换模型会释放正在使用的显存（计划：`threading.Lock` + Gradio `concurrency_limit=1`）
2. segment 字典应升级为 `dataclass SubtitleSegment`，消除字段拼写风险
3. `app_ui.py` 单文件 650+ 行，语言切换手工维护 74 个组件映射（计划：按 Tab 拆分 + `gr.I18n`）
4. API Key 明文存于 `config.json`（计划：环境变量 / 系统凭据管理器 + 日志脱敏）
5. 固定边界切块可能切断单词（计划：静音检测对齐切点或重叠合并）
