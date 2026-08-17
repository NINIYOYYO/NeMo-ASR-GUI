# 贡献指南

感谢你对 Parakeet-TDT-GUI 的兴趣！本文档说明如何搭建开发环境、遵循的代码规范与提交流程。

## 开发环境

推荐使用 [uv](https://docs.astral.sh/uv/)：

```bash
git clone https://github.com/NINIYOYYO/parakeet-tdt-0.6b-v2-SRT-GUI.git
cd parakeet-tdt-0.6b-v2-SRT-GUI

uv sync --group dev          # 安装运行依赖 + 开发工具
uv run pre-commit install    # 安装提交钩子（此后每次 commit 自动跑 ruff + mypy）
```

GPU 用户请先按 README 安装匹配 CUDA 版本的 torch。

## 质量门禁

所有提交必须通过以下三项检查（pre-commit 钩子会自动执行前两项）：

```bash
uv run ruff check .   # lint + import 排序，配置见 pyproject.toml [tool.ruff]
uv run mypy           # 类型检查，配置见 pyproject.toml [tool.mypy]
uv run pytest         # 测试套件（无需 GPU：重依赖由 tests/conftest.py 自动打桩）
```

约定：

- **类型标注**：新代码必须带类型标注；可为空的参数写 `str | None = None`，不使用隐式 Optional
- **接口先行**：新增服务/控制器方法时，先在 `interfaces.py` 定义抽象方法，保持接口与实现签名一致
- **不跨层调私有方法**：controller 只调用 service 的公开 API（无下划线前缀）
- **错误处理**：service 层记录日志并返回错误信息或抛领域异常（`utils/exceptions.py`）；不静默吞错
- **国际化**：新增 UI 文案必须同时更新 `locales/` 下全部四个语言文件（zh/en/ja/ko）

## 测试

- 纯逻辑（字幕格式、断句算法、配置管理）优先写单元测试，放在 `tests/`
- UI 布局与事件绑定的回归由 `tests/test_smoke.py` 保护——修改 `app_ui.py` 后务必跑一遍
- 涉及 LLM API 的逻辑用 `respx` mock HTTP，不要在测试中真实调用外部 API

## 分支与提交

- `main` 为稳定分支；功能开发使用 `feat/<名称>`，修复使用 `fix/<名称>`
- 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)：
  - `feat: 新增 VTT 解析支持`
  - `fix: 修复批量转录中断问题`
  - `docs:` / `chore:` / `refactor:` / `test:` 同理
- PR 请附上变更说明与测试方式；界面变动建议附截图

## 安全红线

- **绝不提交密钥**：`config.json` 已被 `.gitignore` 忽略，请勿强制添加；代码与日志中不得出现明文 API Key
- 个人产出（`subtitles/`、`logs/`）与模型文件（`*.nemo`、`models--*/`）不入库
