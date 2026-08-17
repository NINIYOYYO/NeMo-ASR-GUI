# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- `tests/`：端到端冒烟测试套件（8 个用例），重依赖自动打桩，无需 GPU/NeMo 即可运行
- 文档：`LICENSE`、`CHANGELOG.md`、`CONTRIBUTING.md`、`docs/architecture.md`；README 全面翻新

## [0.2.0] - 2026-07-26

### Added
- `pyproject.toml`：完整项目元数据与依赖声明，ruff / mypy / pytest 配置集中管理，dev 依赖组
- `.pre-commit-config.yaml`：提交钩子（ruff + mypy + 基础检查）
- `ISubtitleGenerator` 新增公开 API `format_time` / `srt_time_to_seconds`

### Fixed
- 配置键名不匹配导致"音频分块长度"滑块的值永远无法保存（`chunk_length` → `chunk_length_s`）
- 切换界面语言会用启动时的旧值回滚本次会话已更新的模型配置（现在只保存 `language`）
- 配置中 `language` / `cloud_model_name` 为 null 时加载 `locales/None.json`、界面显示原始翻译键
- 本地模型加载失败（文件损坏等）导致程序启动崩溃；改为返回错误信息并在界面提示
- 批量转录中单个文件音频提取失败会中止整个队列；最后一个文件失败时已生成的字幕不显示在下载列表
- 字幕编辑器"批量替换"按钮被重复绑定，每次点击执行两遍
- 缺少 `logging_filter_config.yaml` 时因函数定义顺序问题启动崩溃
- 字幕时间戳毫秒浮点截断误差（如 1.001s 输出为 `00:00:01,000`）
- `interfaces.py` 与实现的签名漂移（`process_media` / `handle_translation` 等）

### Security
- `.gitignore` 补充 `config.json`（含 API Key）、`logs/`、`subtitles/`、`*.nemo` 等，防止敏感信息与大文件入库

## [0.1.0] - 2026-02-04

### Added
- 转录、字幕编辑、LLM 翻译、AI 断句四大功能；多格式导出；四语言界面（历史版本）
