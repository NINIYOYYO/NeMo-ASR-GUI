# Parakeet-TDT-GUI: 智能语音转录与字幕工作站

<p align="center">
  <img src="https://img.shields.io/badge/Model-NVIDIA%20Parakeet-green" alt="Model">
  <img src="https://img.shields.io/badge/Framework-NeMo%20%2F%20Gradio-orange" alt="Framework">
  <img src="https://img.shields.io/badge/License-MIT-blue" alt="License">
</p>

<p align="center">
  <a href="./README_en.md">English</a>
  <a href="./README_ko.md">한국어</a> 
  <a href="./README_ja.md">日本語</a>
</p>

**Parakeet-TDT-GUI** 是一个功能强大的本地化视听处理工作站。它基于 **NVIDIA NeMo** 框架和 **Parakeet-TDT** 系列模型，不仅能提供极速、高精度的语音识别（ASR），还集成了 **LLM（大语言模型）翻译**、**智能断句** 以及 **可视化的字幕校对编辑器**。

本项目旨在为字幕组、视频创作者和语言学习者提供一站式的“转录-校对-翻译-导出”解决方案。

## ✨ 核心特性 ()

### 1. 极致转录 (ASR)
*   **多模型支持**: 集成 NVIDIA 最新的 Parakeet TDT 系列模型：
    *   `0.6b-v2`: 英语识别综合能力最强。
    *   `0.6b-v3`: 支持 **20+ 种语言**（英/德/法/俄/日/西等）。
    *   `ctc-110m`: 超轻量级，低显存极速推理。
    *   `0.6b-ja`: 针对 **日语** 优化的专用模型。
*   **多格式导出**: 支持导出 `SRT`, `VTT`, `ASS` (特效字幕), `LRC` (歌词), `TXT`, `JSON`。
*   **微秒级精度**: 支持 **逐词 (Word-level)** 和 **逐字 (Character-level)** 时间戳输出，适合制作卡拉OK或精确对齐。
*   **智能排版**: 内置智能拆分逻辑，可限制单行最大字符数，防止字幕超长。

### 2. LLM 智能翻译
*   **多模型兼容**: 兼容 OpenAI 格式接口（支持 **DeepSeek**、**ChatGPT**、**Claude** 等）及 Google Gemini 原生接口。
*   **双语字幕**: 支持生成“原文+译文”的双语对照字幕。
*   **防错位算法**: 采用 ID-Mapping 映射技术，彻底解决大模型翻译时行数不匹配和时间轴错位的问题。
*   **高并发**: 支持多线程并发翻译，大幅提升长视频处理速度。

### 3. 可视化字幕编辑器
*   **校对表格**: 类似 Excel 的界面，直接在网页上修改时间轴和文本。
*   **批量修正**: 支持定义“错误-正确”对照表（如将“Parakeet”统一修正为“鹦鹉”），一键批量替换全文。
*   **校对本记忆**: 自动保存你的校对规则，越用越顺手。

### 4. AI 智能断句
*   针对 ASR 生成的大段不换行文本，利用 LLM 的语义理解能力进行智能切分，自动匹配原始时间轴，生成符合人类阅读习惯的短句字幕。


---

## 环境要求

*   **操作系统**: Windows / Linux
*   **Python**: 3.10 - 3.12
*   **显卡**: 推荐拥有 **4GB+ 显存** 的 NVIDIA 显卡（支持 CUDA）。
    *   *注：无显卡也可使用 CPU 模式，但速度较慢。*
*   **FFmpeg**: **必须安装** 并配置到系统环境变量（用于音频提取）。
### 安装前提： 如果是在windows下依赖安装失败请确保电脑有**Visual Studio**能够编译


---

## 🚀 安装指南 (Windows)

### 方法一：使用批处理脚本 (小白推荐)

1.  **克隆/下载本项目**到本地。
2.  双击运行 **`install_dependencies.bat`**。
    *   脚本会自动创建 Python 虚拟环境。
    *   自动安装所需的依赖库。
3.  安装完成后，双击 **`launcher.bat`** 即可启动程序。

> **注意**: 如果你需要 GPU 加速，建议参考“方法二”手动安装 PyTorch，以确保 CUDA 版本匹配。

### 方法二：手动命令行安装 (推荐)

1.  **克隆仓库:**
    ```bash
    git clone https://github.com/NINIYOYYO/NeMo-ASR-GUI.git
    cd NeMo-ASR-GUI.git
    ```

2.  **创建并激活虚拟环境:**
    ```bash
    python -m venv .venv
    # Windows:
    .\.venv\Scripts\activate
    # Linux/Mac:
    source .venv/bin/activate
    ```



3.  **安装 PyTorch (重要：GPU 用户请特别注意!):**
    如果你希望使用 NVIDIA GPU 进行加速处理 (强烈推荐)，**请务必在安装其他依赖项之前，先手动安装一个与你的 CUDA 环境兼容的 PyTorch 版本。**
    *   输入Win+R键打开windows系统的运行窗口输入CMD进入终端输入
    ```bash
    nvidia-smi
    ```
    并且回车来检查你的 CUDA Version:
    *   访问 [PyTorch 官网安装指引页面](https://pytorch.org/get-started/locally/)。
    *   根据你的操作系统、包管理器 (推荐 `pip`)、计算平台 (例如 CUDA 11.8, CUDA 12.1) 和 Python 版本选择正确的安装命令。
    *   例如，如果使用 `pip` 且你的系统有 CUDA 12.1 环境，可以运行：
        ```bash
        pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
        ```
    如果跳过此步骤，或者你的系统没有 NVIDIA GPU，后续安装的 `nemo_toolkit` 可能会默认安装仅支持 CPU 的 PyTorch 版本。

4.  **安装项目其他依赖:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **安装 FFmpeg:**
    *   **Windows**: 下载 FFmpeg 预编译包，解压并将 `bin` 文件夹路径添加到系统的 `Path` 环境变量中。
    *   打开终端输入 `ffmpeg -version`，如果有输出则说明安装成功。

6.  **启动程序:**
    ```bash
    python main.py
    ```
---    
## 📖 使用教程

### 1. 模型加载 (Model Loading)
进入 **"模型设置"** 区域：
*   **云端模型**: 选择模型（如 `nvidia/parakeet-tdt-0.6b-v2`），点击加载。首次会自动下载（约1-2GB）。
*   **本地模型**: 输入 `.nemo` 文件的绝对路径，点击加载。

### 2. 字幕生成 (Transcription)
1.  上传视频/音频文件（支持批量）。
2.  **分块长度**: 建议 60-180秒。
3.  **输出格式**: 勾选需要的格式（推荐 `srt` 和 `ass`）。
4.  **高级选项**:
    *   *逐字/逐词*: 需要卡拉OK效果时勾选。
    *   *智能拆分*: 开启并设置“最大行宽”（如 40字符），自动将长句切分为双行。
5.  点击 **"开始生成"**。

### 3. 字幕编辑 (Editing)
1.  在 **"字幕编辑"** 标签页上传刚才生成的 SRT 文件。
2.  **批量校对**: 在左侧“校对表”中输入常错词和正确词，点击“批量替换”。
3.  **手动微调**: 在下方表格中直接修改文字或时间。
4.  点击 **"保存字幕文件"** 导出修改后的版本。

### 4. AI 翻译 (Translation)
1.  切换到 **"AI 翻译"** 标签页。
2.  填写 LLM 配置：
    *   **API Key**: 你的 OpenAI/DeepSeek/Gemini 密钥。
    *   **Base URL**: 例如 `https://api.deepseek.com` 或 `https://generativelanguage.googleapis.com/v1beta`。
    *   **Model**: 例如 `deepseek-chat` 或 `gemini-3.0-flash`。
3.  设置 **目标语言** 和 **是否双语**。
4.  点击开始，系统将自动并行翻译并生成新文件。

### 5. AI 断句 (Segmentation)
*   适用于 ASR 生成的字幕虽然文字对但在时间轴上“一句话太长”的情况。
*   上传字幕，配置 LLM，点击开始，AI 会根据语义重新切分时间轴。

---
## 界面展示
!["界面"](./README.assets/2.png)


## 📂 项目结构

```text
D:\PROGRAMING\PARAKEET-TDT-0.6B-V2-SRT-GUI
│  application.py           # 应用核心编排
│  app_ui.py                # Gradio UI 布局与交互
│  main.py                  # 启动入口
│  config.json              # 用户配置文件
│  
├─controllers/              # 业务逻辑控制器
│      model_controller.py
│      subtitle_editor_controller.py
│      transcription_controller.py
│      translation_controller.py
│      
├─core/                     # 核心服务
│      asr_service.py       # NeMo 模型推理封装
│      audio_processor.py   # FFmpeg 音频处理
│      post_processors.py   # 后处理策略 (日语优化/断句)
│      subtitle_generator.py# 字幕格式生成 (SRT/ASS/VTT等)
│      translation_service.py # LLM 翻译与断句服务
│      
├─interfaces/               # 接口定义
├─locales/                  # 多语言界面翻译
├─subtitles/                # 输出目录
│  ├─edited/                # 编辑后的字幕
│  └─translated/            # 翻译后的字幕
│      
└─utils/                    # 工具类 (日志、配置、异常)
```

## ⚠️ 常见问题 (FAQ)

**Q: 为什么生成的字幕全是乱码或者时间轴重叠？**
A: 请检查是否使用了不匹配语言的模型。例如，用英语模型转录中文音频会导致不可预测的结果。请使用 `0.6b-v3` (多语言) 或专用模型。

**Q: 翻译功能报错 "429 Too Many Requests"？**
A: 这是 API 调用频率限制。请在界面上调低 **"并发数 (Concurrency)"** 滑块，或者增加 **"分块大小"**。

**Q: 程序提示找不到 FFmpeg？**
A: 请确保在 CMD 中输入 `ffmpeg` 能看到版本信息。如果刚安装，请重启电脑或 IDE。

**Q: 显存爆了 (OOM) 怎么办？**
A: 1. 减小“音频分块长度” (例如设为 30s)。2. 使用更小的模型 (`ctc-110m`)。

---

## 🤝 贡献与协议

本项目基于 MIT 协议开源。核心模型版权归 NVIDIA 所有。
欢迎提交 Issue 反馈 Bug 或提交 Pull Request 增加新功能！